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
from skill_genome import retention_update


LOGGER = logging.getLogger("cas_fabric.task_coordinator")
PROTOCOL_VERSION = "cas-fabric.task-auction.v0.1"


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
            valid_proposals = self.validate_proposals(goal_id, required_skills, proposals)
            assignments = self.resolve_assignments(goal_id, required_skills, valid_proposals)

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
            assigned_skills = {
                skill
                for assignment in assignments
                for skill in assignment.get("skills_assigned", [])
            }
            unassigned_skills = sorted(set(required_skills) - assigned_skills)
            execution_ok = all(item.get("ok") for item in execution)
            result = {
                "ok": bool(assignments) and not unassigned_skills and execution_ok,
                "type": "goal.result",
                "protocol": PROTOCOL_VERSION,
                "goal_id": goal_id,
                "required_skills": required_skills,
                "proposal_count": len(proposals),
                "valid_proposal_count": len(valid_proposals),
                "proposals": valid_proposals,
                "assignments": assignments,
                "unassigned_skills": unassigned_skills,
                "execution": execution,
            }
        except Exception as exc:
            LOGGER.exception("goal.submit failed")
            result = {"ok": False, "error": str(exc)}

        if respond:
            await respond(result)

    @staticmethod
    def validate_proposals(
        goal_id: str,
        required_skills: list[str],
        proposals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        required = set(required_skills)
        valid: list[dict[str, Any]] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for proposal in proposals:
            if proposal.get("goal_id") != goal_id:
                continue
            node_id = str(proposal.get("node_id", "")).strip()
            if not node_id:
                continue
            offered = sorted(required & {str(skill) for skill in proposal.get("skills_offered", [])})
            if not offered:
                continue
            confidence = float(proposal.get("confidence", 0.0))
            if confidence < 0.5:
                continue
            key = (node_id, tuple(offered))
            if key in seen:
                continue
            seen.add(key)
            valid.append(
                {
                    "type": "goal.proposal",
                    "protocol": str(proposal.get("protocol", PROTOCOL_VERSION)),
                    "goal_id": goal_id,
                    "node_id": node_id,
                    "skills_offered": offered,
                    "skill_manifests": TaskCoordinator.select_skill_manifests(
                        offered,
                        proposal.get("skill_manifests", []),
                    ),
                    "estimated_latency_ms": int(proposal.get("estimated_latency_ms", 999999)),
                    "estimated_energy_cost": float(proposal.get("estimated_energy_cost", 1.0)),
                    "current_load": float(proposal.get("current_load", 1.0)),
                    "confidence": confidence,
                }
            )
        return valid

    @staticmethod
    def select_skill_manifests(
        offered_skills: list[str],
        manifests: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        by_skill = {
            str(manifest.get("skill_id")): manifest
            for manifest in manifests
            if manifest.get("type") == "skill.manifest" and manifest.get("skill_id")
        }
        selected: list[dict[str, Any]] = []
        for skill in offered_skills:
            manifest = by_skill.get(skill)
            if not manifest:
                continue
            if manifest.get("capability") != skill:
                continue
            if "retention_hints" not in manifest:
                continue
            selected.append(manifest)
        return selected

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
            manifests = [
                manifest for manifest in proposal.get("skill_manifests", [])
                if manifest.get("skill_id") in selected
            ]
            assignments.append(
                {
                    "goal_id": goal_id,
                    "type": "goal.assignment",
                    "protocol": PROTOCOL_VERSION,
                    "node_id": proposal.get("node_id"),
                    "skills_assigned": selected,
                    "skill_manifests": manifests,
                    "execution_order": len(assignments),
                    "dependencies": [],
                    "confidence": proposal.get("confidence", 0.0),
                }
            )
            remaining -= set(selected)
            if not remaining:
                break
        return assignments

    async def execute_assignments(self, intent: str, assignments: list[dict[str, Any]]) -> list[dict]:
        results: list[dict] = []
        for assignment in assignments:
            manifests = {
                manifest.get("skill_id"): manifest
                for manifest in assignment.get("skill_manifests", [])
            }
            for skill in assignment.get("skills_assigned", []):
                timeout = 180 if skill == "reasoning.llm" else 30
                try:
                    if skill == "memory.query":
                        response = await self.fabric.request("memory.query", {"query": intent, "limit": 3}, timeout=timeout)
                    elif skill == "reasoning.llm":
                        response = await self.fabric.request(
                            "reasoning.llm",
                            {"intent": intent, "memory_limit": 3},
                            timeout=timeout,
                        )
                    else:
                        response = {"ok": False, "error": f"no executor mapping for skill {skill}"}
                    ok = bool(response and response.get("ok"))
                    error = None if ok else str((response or {}).get("error", "skill returned non-ok response"))
                except asyncio.TimeoutError:
                    response = None
                    ok = False
                    error = f"skill timed out after {timeout}s"
                except Exception as exc:
                    response = None
                    ok = False
                    error = str(exc)
                results.append(
                    {
                        "type": "assignment.execution_result",
                        "protocol": PROTOCOL_VERSION,
                        "goal_id": assignment.get("goal_id"),
                        "node_id": assignment.get("node_id"),
                        "skill": skill,
                        "ok": ok,
                        "error": error,
                        "retention_update": retention_update(manifests.get(skill, {"skill_id": skill}), ok),
                        "response": response,
                    }
                )
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
