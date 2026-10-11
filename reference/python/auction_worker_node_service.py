"""
Milestone 2 Auction Worker.

Subscribes to goal.broadcast and proposes its configured skills.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import os
import signal
import uuid
from collections import OrderedDict

from fabric_nats import NATSFabric
from skill_genome import manifests_for_skills


LOGGER = logging.getLogger("cas_fabric.auction_worker")
PROTOCOL_VERSION = "cas-fabric.task-auction.v0.1"


class AuctionWorker:
    def __init__(self) -> None:
        self.fabric = NATSFabric()
        self.node_id = os.environ.get("CAS_WORKER_ID", "worker-unspecified")
        self.skills = [
            skill.strip()
            for skill in os.environ.get("CAS_WORKER_SKILLS", "").split(",")
            if skill.strip()
        ]
        self.estimated_latency_ms = int(os.environ.get("CAS_WORKER_LATENCY_MS", "100"))
        self.current_load = float(os.environ.get("CAS_WORKER_LOAD", "0.1"))
        self.skill_manifests = manifests_for_skills(self.skills)
        if not self.node_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in self.node_id):
            raise ValueError("worker ID must be a safe NATS subject token")
        self.execution_capability = "auction.execute." + self.node_id + "." + uuid.uuid4().hex
        self.assignments: OrderedDict[str, dict] = OrderedDict()

    async def start(self) -> None:
        if not self.skills:
            raise RuntimeError("CAS_WORKER_SKILLS must not be empty")
        await self.fabric.connect()
        await self.fabric.subscribe_async("goal.broadcast", self.handle_goal)
        await self.fabric.subscribe_async(f"goal.assignment.{self.node_id}", self.handle_assignment)
        await self.fabric.subscribe_async(f"capability.{self.execution_capability}", self.handle_execute)
        LOGGER.info("Auction worker ready: node_id=%s skills=%s", self.node_id, self.skills)

    async def handle_goal(self, message: dict) -> None:
        if len(self.assignments) >= 1024 and self.completed_assignment() is None:
            return
        payload = message.get("payload", {})
        required = set(payload.get("required_skills", []))
        offered = sorted(required & set(self.skills))
        if not offered:
            return
        offered_manifests = [
            manifest for manifest in self.skill_manifests
            if manifest.get("skill_id") in offered
        ]
        proposal_subject = payload.get("proposal_subject")
        if not proposal_subject:
            return
        await self.fabric.publish(
            proposal_subject,
            {
                "type": "goal.proposal",
                "protocol": PROTOCOL_VERSION,
                "goal_id": payload.get("goal_id"),
                "node_id": self.node_id,
                "execution_capability": self.execution_capability,
                "skills_offered": offered,
                "skill_manifests": offered_manifests,
                "estimated_latency_ms": self.estimated_latency_ms,
                "estimated_energy_cost": 0.1,
                "current_load": self.current_load,
                "confidence": 0.99,
            },
        )

    def completed_assignment(self) -> str | None:
        return next((key for key, value in self.assignments.items()
                     if value["finished"] == set(value["skills"])), None)

    async def handle_assignment(self, message: dict) -> None:
        payload = message.get("payload", {})
        assignment = payload.get("assignment", {})
        goal_id = payload.get("goal_id")
        skills = assignment.get("skills_assigned", [])
        if (not goal_id or not isinstance(skills, list) or not skills or
                not set(skills).issubset(self.skills) or
                assignment.get("node_id") != self.node_id or
                assignment.get("execution_capability") != self.execution_capability):
            LOGGER.warning("Rejected assignment for this worker")
            return
        if goal_id in self.assignments:
            return
        if len(self.assignments) >= 1024:
            completed = self.completed_assignment()
            if completed is None:
                LOGGER.error("Worker assignment capacity exhausted")
                return
            del self.assignments[completed]
        self.assignments[goal_id] = {"intent": payload.get("intent"), "skills": copy.deepcopy(skills),
                                     "started": set(), "finished": set()}

    async def execute_skill(self, skill: str, intent: str) -> dict | None:
        if skill == "memory.query":
            return await self.fabric.request(skill, {"query": intent, "limit": 3}, timeout=30)
        if skill == "reasoning.llm":
            return await self.fabric.request(skill, {"intent": intent, "memory_limit": 3}, timeout=180)
        return {"ok": False, "error": f"no executor mapping for skill {skill}"}

    async def handle_execute(self, message: dict) -> None:
        payload = message.get("payload", {})
        respond = message.get("respond")
        goal_id, skill = payload.get("goal_id"), payload.get("skill")
        result = {"ok": False, "node_id": self.node_id, "goal_id": goal_id, "skill": skill}
        record = self.assignments.get(goal_id)
        accepted = False
        try:
            if (not record or payload.get("node_id") != self.node_id or
                    payload.get("intent") != record["intent"] or skill not in record["skills"]):
                raise ValueError("execution does not match a recorded assignment")
            if skill in record["started"]:
                raise ValueError("assignment skill has already started")
            record["started"].add(skill)
            accepted = True
            response = await self.execute_skill(skill, record["intent"])
            result["response"] = response
            result["ok"] = isinstance(response, dict) and response.get("ok") is True
            if not result["ok"]:
                result["error"] = (response or {}).get("error", "skill returned non-ok response")
        except Exception as exc:
            result["error"] = str(exc)
            LOGGER.warning("Worker execution failed: %s", exc)
        finally:
            if accepted:
                record["finished"].add(skill)
        if respond:
            await respond(result)

    async def close(self) -> None:
        await self.fabric.close()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    worker = AuctionWorker()
    await worker.start()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()
    await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
