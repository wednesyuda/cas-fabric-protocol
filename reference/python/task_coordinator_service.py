"""
Milestone 2 Task Coordinator.

Exposes:
  - goal.submit

Implements the first minimal Task Auction:
  goal.submit -> goal.broadcast -> goal.proposal.* -> goal.assignment.*
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import uuid
from typing import Any

from fabric_nats import NATSFabric


LOGGER = logging.getLogger("cas_fabric.task_coordinator")


class TaskCoordinator:
    def __init__(self) -> None:
        self.fabric = NATSFabric()

    async def start(self) -> None:
        await self.fabric.connect()
        await self.fabric.subscribe_async("capability.goal.submit", self.handle_goal)
        LOGGER.info("Task coordinator ready: capability=goal.submit")

    async def handle_goal(self, message: dict) -> None:
        respond = message.get("respond")
        payload = message.get("payload", {})
        try:
            intent = str(payload["intent"]).strip()
            required_skills = [str(s) for s in payload.get("required_skills", [])]
            if not intent:
                raise ValueError("intent must not be empty")
            if not required_skills:
                raise ValueError("required_skills must not be empty")

            goal_id = str(uuid.uuid4())
            proposal_subject = f"goal.proposal.{goal_id}"
            proposals: list[dict[str, Any]] = []

            await self.fabric.subscribe_async(
                proposal_subject,
                lambda msg: proposals.append(msg["payload"]),
            )

            await self.fabric.publish(
                "goal.broadcast",
                {
                    "type": "goal.broadcast",
                    "goal_id": goal_id,
                    "intent": intent,
                    "required_skills": required_skills,
                    "deadline_ms": int(payload.get("deadline_ms", 0)),
                    "priority": str(payload.get("priority", "medium")),
                    "proposal_subject": proposal_subject,
                },
            )

            await asyncio.sleep(float(payload.get("proposal_window_ms", 1000)) / 1000.0)
            assignments = self.resolve_assignments(goal_id, required_skills, proposals)

            for assignment in assignments:
                await self.fabric.publish(
                    f"goal.assignment.{assignment['node_id']}",
                    {
                        "type": "goal.assignment",
                        "goal_id": goal_id,
                        "assignment": assignment,
                    },
                )

            execution = await self.execute_assignments(intent, assignments)
            result = {
                "ok": bool(assignments),
                "goal_id": goal_id,
                "required_skills": required_skills,
                "proposal_count": len(proposals),
                "proposals": proposals,
                "assignments": assignments,
                "execution": execution,
            }
        except Exception as exc:
            LOGGER.exception("goal.submit failed")
            result = {"ok": False, "error": str(exc)}

        if respond:
            await respond(result)

    @staticmethod
    def resolve_assignments(
        goal_id: str,
        required_skills: list[str],
        proposals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        remaining = set(required_skills)
        assignments: list[dict[str, Any]] = []
        ranked = sorted(
            proposals,
            key=lambda p: (
                float(p.get("current_load", 1.0)),
                int(p.get("estimated_latency_ms", 999999)),
                str(p.get("node_id", "")),
            ),
        )
        for proposal in ranked:
            offered = set(proposal.get("skills_offered", []))
            selected = sorted(remaining & offered)
            if not selected:
                continue
            assignments.append(
                {
                    "goal_id": goal_id,
                    "node_id": proposal.get("node_id"),
                    "skills_assigned": selected,
                    "execution_order": len(assignments),
                    "dependencies": [],
                }
            )
            remaining -= set(selected)
            if not remaining:
                break
        return assignments

    async def execute_assignments(self, intent: str, assignments: list[dict[str, Any]]) -> list[dict]:
        results: list[dict] = []
        for assignment in assignments:
            for skill in assignment.get("skills_assigned", []):
                if skill == "memory.query":
                    response = await self.fabric.request("memory.query", {"query": intent, "limit": 3}, timeout=30)
                elif skill == "reasoning.llm":
                    response = await self.fabric.request(
                        "reasoning.llm",
                        {"intent": intent, "memory_limit": 3},
                        timeout=180,
                    )
                else:
                    response = {"ok": False, "error": f"no executor mapping for skill {skill}"}
                results.append({"skill": skill, "response": response})
        return results

    async def close(self) -> None:
        await self.fabric.close()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    coordinator = TaskCoordinator()
    await coordinator.start()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()
    await coordinator.close()


if __name__ == "__main__":
    asyncio.run(main())
