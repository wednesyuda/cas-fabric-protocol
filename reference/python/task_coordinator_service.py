"""
Milestone 2 Task Coordinator.

Exposes:
  - goal.submit

Implements the first minimal Task Auction:
  goal.submit -> goal.broadcast -> goal.proposal.* -> goal.assignment.*
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import os
import signal
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fabric_nats import NATSFabric
from request_budget import remaining
from state_lock import StateLocks
from skill_genome import retention_update


LOGGER = logging.getLogger("cas_fabric.task_coordinator")
PROTOCOL_VERSION = "cas-fabric.task-auction.v0.1"
GOAL_PROTOCOL_VERSION = "cas-fabric.goal-system.v0.1"
REFLECTION_PROTOCOL_VERSION = "cas-fabric.reflection.v0.1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def save_json(path: Path, data: dict) -> None:
    """Commit one store snapshot atomically; one coordinator owns each file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         delete=False) as stream:
            temp_path = Path(stream.name)
            json.dump(data, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def validate_goal_fields(intent, required_skills, priority) -> None:
    if not isinstance(intent, str) or not intent.strip():
        raise ValueError("intent must be a non-empty string")
    if (not isinstance(required_skills, list) or not required_skills or
            any(not isinstance(skill, str) or not skill.strip() for skill in required_skills)):
        raise ValueError("required_skills must be a non-empty list of strings")
    if priority not in ("low", "medium", "high"):
        raise ValueError("priority must be low, medium, or high")


class GoalStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.getenv("CAS_GOAL_STORE_PATH", "/tmp/cas-fabric-goals.json"))
        self.goals: dict[str, dict[str, Any]] = {}

    def load(self) -> None:
        if self.path.exists():
            self.goals = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        save_json(self.path, self.goals)

    def recover_inflight(self) -> None:
        """Do not replay potentially completed external work after restart."""
        for goal_id, goal in list(self.goals.items()):
            if goal["state"] in ("broadcast", "assigned", "executing"):
                self.transition(goal_id, "failed", reason="coordinator_restart")

    def _commit(self, goal_id: str, goal: dict) -> dict:
        goals = {**self.goals, goal_id: goal}
        save_json(self.path, goals)
        self.goals = goals
        return copy.deepcopy(goal)

    def create(self, intent: str, required_skills: list[str], priority: str = "medium") -> dict[str, Any]:
        validate_goal_fields(intent, required_skills, priority)
        goal_id = str(uuid.uuid4())
        timestamp = now_iso()
        goal = {
            "type": "goal",
            "protocol": GOAL_PROTOCOL_VERSION,
            "goal_id": goal_id,
            "intent": intent,
            "required_skills": list(required_skills),
            "priority": priority,
            "state": "created",
            "created_at": timestamp,
            "updated_at": timestamp,
            "history": [{"state": "created", "timestamp": timestamp}],
        }
        return self._commit(goal_id, goal)

    def get(self, goal_id: str) -> dict[str, Any] | None:
        return copy.deepcopy(self.goals.get(goal_id))

    def transition(self, goal_id: str, state: str, **metadata: Any) -> dict[str, Any]:
        return self.update(goal_id, {"state": state}, **metadata)

    def update(self, goal_id: str, patch: dict[str, Any], **metadata: Any) -> dict[str, Any]:
        if not isinstance(patch, dict):
            raise ValueError("patch must be an object")
        goal = copy.deepcopy(self.goals[goal_id])
        state = patch.get("state", goal["state"])
        allowed = {
            "created": {"broadcast", "suspended", "completed", "failed"},
            "broadcast": {"assigned", "failed"},
            "assigned": {"executing", "failed"},
            "executing": {"completed", "failed"},
            "completed": set(), "failed": set(), "suspended": set(),
        }
        if goal["state"] in ("completed", "failed", "suspended"):
            raise ValueError("terminal goal is immutable")
        if state != goal["state"] and state not in allowed[goal["state"]]:
            raise ValueError(f"invalid transition: {goal['state']} -> {state}")
        if goal["state"] != "created" and any(
                key in patch for key in ("intent", "required_skills", "priority")):
            raise ValueError("execution fields may only be edited while goal is created")
        for key in ("intent", "required_skills", "priority"):
            if key in patch:
                goal[key] = copy.deepcopy(patch[key])
        validate_goal_fields(goal["intent"], goal["required_skills"], goal["priority"])
        timestamp = now_iso()
        goal["state"] = state
        goal["updated_at"] = timestamp
        event = {"state": state, "timestamp": timestamp}
        event_metadata = copy.deepcopy(metadata)
        if any(key != "state" for key in patch):
            event_metadata["patch"] = copy.deepcopy(patch)
        if event_metadata:
            event["metadata"] = event_metadata
            goal.setdefault("metadata", {}).update(event_metadata)
        goal.setdefault("history", []).append(event)
        return self._commit(goal_id, goal)


class ReflectionStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.getenv("CAS_REFLECTION_STORE_PATH", "/tmp/cas-fabric-reflections.json"))
        self.skills: dict[str, dict[str, Any]] = {}

    def load(self) -> None:
        if self.path.exists():
            self.skills = json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        save_json(self.path, self.skills)

    def status(self, skill_id: str, node_id: str | None = None) -> dict[str, Any]:
        default = {
                "type": "skill.reflection_status",
                "protocol": REFLECTION_PROTOCOL_VERSION,
                "skill_id": skill_id,
                "attempt_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "adaptive_confidence": 0.5,
                "last_goal_id": None,
                "last_outcome": None,
                "lifecycle_recommendation": "observe",
            }
        status = self.skills.get(skill_id, default)
        if node_id is not None:
            return status.get("nodes", {}).get(node_id, {**default, "node_id": node_id})
        return status

    def record_execution(self, goal_id: str, execution: list[dict[str, Any]]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        skills = copy.deepcopy(self.skills)
        for item in execution:
            skill_id = str(item.get("skill", ""))
            if not skill_id:
                continue
            current = skills.get(skill_id, self.status(skill_id))
            success = bool(item.get("ok"))
            previous = float(current.get("adaptive_confidence", 0.5))
            delta = 0.05 if success else -0.10
            updated = min(1.0, max(0.0, previous + delta))
            status = {
                **current,
                "attempt_count": int(current.get("attempt_count", 0)) + 1,
                "success_count": int(current.get("success_count", 0)) + (1 if success else 0),
                "failure_count": int(current.get("failure_count", 0)) + (0 if success else 1),
                "adaptive_confidence": round(updated, 3),
                "last_goal_id": goal_id,
                "last_outcome": "success" if success else "failure",
                "lifecycle_recommendation": "prefer" if updated >= 0.6 else "observe" if updated >= 0.3 else "deprioritize",
                "score_basis": "execution_status_not_answer_correctness",
            }
            node_id = item.get("node_id")
            if isinstance(node_id, str) and node_id:
                nodes = status.setdefault("nodes", {})
                node = nodes.get(node_id, self.status(skill_id, node_id))
                node_updated = min(1.0, max(0.0, float(node["adaptive_confidence"]) + delta))
                nodes[node_id] = {
                    **node,
                    "attempt_count": int(node["attempt_count"]) + 1,
                    "success_count": int(node["success_count"]) + int(success),
                    "failure_count": int(node["failure_count"]) + int(not success),
                    "adaptive_confidence": round(node_updated, 3),
                    "last_goal_id": goal_id,
                    "last_outcome": "success" if success else "failure",
                    "lifecycle_recommendation": "prefer" if node_updated >= 0.6 else "observe" if node_updated >= 0.3 else "deprioritize",
                    "score_basis": "execution_status_not_answer_correctness",
                }
            skills[skill_id] = status
            events.append(
                {
                    "type": "reflection.event",
                    "protocol": REFLECTION_PROTOCOL_VERSION,
                    "goal_id": goal_id,
                    "skill_id": skill_id,
                    "success": success,
                    "previous_adaptive_confidence": previous,
                    "confidence_delta": delta,
                    "adaptive_confidence": status["adaptive_confidence"],
                    "lifecycle_recommendation": status["lifecycle_recommendation"],
                }
            )
        save_json(self.path, skills)
        self.skills = skills
        return events


class TaskCoordinator:
    def __init__(self) -> None:
        self.fabric = NATSFabric()
        self.goals = GoalStore()
        self.reflections = ReflectionStore()
        self.state_locks = StateLocks([self.goals.path, self.reflections.path])

    async def start(self) -> None:
        self.state_locks.acquire()
        try:
            await self._start()
        except BaseException:
            self.state_locks.close()
            await self.fabric.close()
            raise

    async def _start(self) -> None:
        self.goals.load()
        self.goals.recover_inflight()
        self.reflections.load()
        await self.fabric.connect()
        await self.fabric.subscribe_async("capability.goal.create", self.handle_goal_create)
        await self.fabric.subscribe_async("capability.goal.status", self.handle_goal_status)
        await self.fabric.subscribe_async("capability.goal.update", self.handle_goal_update)
        await self.fabric.subscribe_async("capability.goal.complete", self.handle_goal_complete)
        await self.fabric.subscribe_async("capability.reflection.status", self.handle_reflection_status)
        await self.fabric.subscribe_async("capability.goal.submit", self.handle_goal, max_active=1, max_queued=2, max_queue_wait=15)
        LOGGER.info("Task coordinator ready: capability=goal.submit")

    async def handle_goal_create(self, message: dict) -> None:
        respond = message.get("respond")
        payload = message.get("payload", {})
        try:
            intent = payload["intent"]
            required_skills = payload.get("required_skills", [])
            if not intent:
                raise ValueError("intent must not be empty")
            if not required_skills:
                raise ValueError("required_skills must not be empty")
            goal = self.goals.create(intent, required_skills, str(payload.get("priority", "medium")))
            result = {"ok": True, "goal": goal}
        except Exception as exc:
            LOGGER.exception("goal.create failed")
            result = {"ok": False, "error": str(exc)}
        if respond:
            await respond(result)

    async def handle_goal_status(self, message: dict) -> None:
        respond = message.get("respond")
        payload = message.get("payload", {})
        try:
            goal_id = str(payload["goal_id"])
            goal = self.goals.get(goal_id)
            if not goal:
                raise KeyError(f"goal not found: {goal_id}")
            result = {"ok": True, "goal": goal}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if respond:
            await respond(result)

    async def handle_goal_update(self, message: dict) -> None:
        respond = message.get("respond")
        payload = message.get("payload", {})
        try:
            goal_id = str(payload["goal_id"])
            if not self.goals.get(goal_id):
                raise KeyError(f"goal not found: {goal_id}")
            goal = self.goals.update(goal_id, payload.get("patch", {}))
            result = {"ok": True, "goal": goal}
        except Exception as exc:
            LOGGER.exception("goal.update failed")
            result = {"ok": False, "error": str(exc)}
        if respond:
            await respond(result)

    async def handle_goal_complete(self, message: dict) -> None:
        respond = message.get("respond")
        payload = message.get("payload", {})
        try:
            goal_id = str(payload["goal_id"])
            if not self.goals.get(goal_id):
                raise KeyError(f"goal not found: {goal_id}")
            goal = self.goals.transition(goal_id, "completed", result=payload.get("result", {}))
            result = {"ok": True, "goal": goal}
        except Exception as exc:
            LOGGER.exception("goal.complete failed")
            result = {"ok": False, "error": str(exc)}
        if respond:
            await respond(result)

    async def handle_reflection_status(self, message: dict) -> None:
        respond = message.get("respond")
        payload = message.get("payload", {})
        try:
            skill_id = str(payload["skill_id"])
            result = {"ok": True, "reflection": self.reflections.status(skill_id, payload.get("node_id"))}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
        if respond:
            await respond(result)

    async def handle_goal(self, message: dict) -> None:
        respond = message.get("respond")
        payload = message.get("payload", {})
        goal_id = ""
        subscription = None
        started = False
        try:
            goal_id = str(payload.get("goal_id") or "")
            if goal_id:
                goal = self.goals.get(goal_id)
                if not goal:
                    raise KeyError(f"goal not found: {goal_id}")
                intent = str(goal["intent"])
                required_skills = [str(s) for s in goal.get("required_skills", [])]
                priority = str(goal.get("priority", payload.get("priority", "medium")))
            else:
                intent = payload["intent"]
                required_skills = payload.get("required_skills", [])
                if not intent:
                    raise ValueError("intent must not be empty")
                if not required_skills:
                    raise ValueError("required_skills must not be empty")
                goal = self.goals.create(intent, required_skills, str(payload.get("priority", "medium")))
                goal_id = goal["goal_id"]
                priority = str(goal["priority"])
            if not intent:
                raise ValueError("intent must not be empty")
            if not required_skills:
                raise ValueError("required_skills must not be empty")
            if goal["state"] != "created":
                raise ValueError("only created goals may be submitted")
            window = float(payload.get("proposal_window_ms", 1000))
            if not 0 <= window <= 30000:
                raise ValueError("proposal_window_ms must be between 0 and 30000")
            self.goals.transition(goal_id, "broadcast")
            started = True
            proposal_subject = f"goal.proposal.{goal_id}"
            proposals: list[dict[str, Any]] = []

            subscription = await self.fabric.subscribe_async(
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
                    "priority": priority,
                    "proposal_subject": proposal_subject,
                },
            )
            await asyncio.sleep(window / 1000.0)
            remaining()
            closed_subscription = subscription
            subscription = None
            await closed_subscription.unsubscribe()
            valid_proposals = self.validate_proposals(goal_id, required_skills, proposals)
            for proposal in valid_proposals:
                scores = [
                    float(self.reflections.status(skill, proposal["node_id"]).get("adaptive_confidence", 0.5))
                    for skill in proposal.get("skills_offered", [])
                ]
                proposal["adaptive_confidence"] = round(sum(scores) / len(scores), 3) if scores else 0.5
            assignments = self.resolve_assignments(goal_id, required_skills, valid_proposals)
            self.goals.transition(goal_id, "assigned", assignment_count=len(assignments))

            for assignment in assignments:
                await self.fabric.publish(
                    f"goal.assignment.{assignment['node_id']}",
                    {
                        "type": "goal.assignment",
                        "goal_id": goal_id,
                        "intent": intent,
                        "assignment": assignment,
                    },
                )

            self.goals.transition(goal_id, "executing")
            execution = await self.execute_assignments(intent, assignments)
            reflection_events = self.reflections.record_execution(goal_id, execution)
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
                "reflection_events": reflection_events,
            }
            final_state = "completed" if result["ok"] else "failed"
            result["goal"] = self.goals.transition(goal_id, final_state, result_summary={
                "proposal_count": len(proposals),
                "valid_proposal_count": len(valid_proposals),
                "assignment_count": len(assignments),
                "execution_ok": execution_ok,
                "unassigned_skills": unassigned_skills,
                "reflection_event_count": len(reflection_events),
            })
        except Exception as exc:
            LOGGER.exception("goal.submit failed")
            result = {"ok": False, "error": str(exc)}
            if started:
                current = self.goals.get(goal_id)
                if current["state"] in ("completed", "failed", "suspended"):
                    result["goal"] = current
                else:
                    result["goal"] = self.goals.transition(goal_id, "failed", error=str(exc))
        finally:
            if subscription is not None:
                try:
                    await subscription.unsubscribe()
                except Exception:
                    LOGGER.exception("proposal subscription cleanup failed")

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
                    "execution_capability": proposal.get("execution_capability"),
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
                -float(p.get("adaptive_confidence", p.get("confidence", 0.0))),
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
                    "execution_capability": proposal.get("execution_capability"),
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
                response = None
                try:
                    route = assignment.get("execution_capability")
                    if not isinstance(route, str) or not route.startswith("auction.execute."):
                        raise ValueError("assignment missing worker execution capability")
                    worker_result = await self.fabric.request(route, {
                        "goal_id": assignment.get("goal_id"), "node_id": assignment.get("node_id"),
                        "skill": skill, "intent": intent}, timeout=timeout + 5)
                    if not isinstance(worker_result, dict):
                        raise RuntimeError("assigned worker unavailable or timed out")
                    if any(worker_result.get(key) != value for key, value in (
                            ("node_id", assignment.get("node_id")), ("goal_id", assignment.get("goal_id")),
                            ("skill", skill))):
                        raise ValueError("worker result identity does not match assignment")
                    response = worker_result.get("response")
                    if worker_result.get("ok") is not True:
                        raise RuntimeError(worker_result.get("error", "worker execution failed"))
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
        try:
            await self.fabric.close()
        finally:
            self.state_locks.close()


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
