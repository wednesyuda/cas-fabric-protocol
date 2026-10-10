"""Goal lifecycle regressions derived from RFC-005 sections 1-4 and 7."""

import copy
import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference" / "python"))
from task_coordinator_service import GoalStore, ReflectionStore, TaskCoordinator


class GoalStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "goals.json"
        self.store = GoalStore(str(self.path))
        self.goal_id = self.store.create("Find records", ["memory.query"])["goal_id"]

    def test_successful_lifecycle_survives_reload(self):
        for state in ("broadcast", "assigned", "executing", "completed"):
            self.store.transition(self.goal_id, state, evidence=state)
        restored = GoalStore(str(self.path))
        restored.load()
        self.assertEqual(restored.get(self.goal_id), self.store.get(self.goal_id))
        self.assertEqual([e["state"] for e in restored.get(self.goal_id)["history"]],
                         ["created", "broadcast", "assigned", "executing", "completed"])

    def test_unknown_goal_transition_rejected(self):
        with self.assertRaises((KeyError, ValueError)):
            self.store.transition("missing", "broadcast")

    def test_invalid_transitions_leave_memory_and_disk_unchanged(self):
        for state in ("invented", "executing", "assigned"):
            with self.subTest(state=state):
                before = copy.deepcopy(self.store.goals)
                disk = self.path.read_bytes()
                with self.assertRaises(ValueError):
                    self.store.transition(self.goal_id, state)
                self.assertEqual(self.store.goals, before)
                self.assertEqual(self.path.read_bytes(), disk)

    def test_external_completion_from_created(self):
        goal = self.store.transition(self.goal_id, "completed", result={"answer": 42})
        self.assertEqual(goal["state"], "completed")
        self.assertEqual(goal["history"][-1]["metadata"]["result"], {"answer": 42})

    def test_terminal_goals_cannot_be_reopened(self):
        for terminal in ("completed", "failed", "suspended"):
            with self.subTest(terminal=terminal):
                goal_id = self.store.create("Work", ["memory.query"])["goal_id"]
                if terminal == "failed":
                    for state in ("broadcast", "assigned", "executing"):
                        self.store.transition(goal_id, state)
                self.store.transition(goal_id, terminal)
                before = copy.deepcopy(self.store.get(goal_id))
                with self.assertRaises(ValueError):
                    self.store.transition(goal_id, "broadcast")
                self.assertEqual(self.store.get(goal_id), before)

    def test_invalid_update_does_not_partially_change_goal(self):
        before = copy.deepcopy(self.store.goals)
        disk = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.store.update(self.goal_id, {"intent": "Changed", "state": "invented"})
        self.assertEqual(self.store.goals, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def test_valid_field_update_records_history_and_preserves_identity(self):
        before = copy.deepcopy(self.store.get(self.goal_id))
        patch = {"intent": "New intent", "priority": "high", "required_skills": ["reasoning.llm"]}
        goal = self.store.update(self.goal_id, patch)
        self.assertEqual(goal["created_at"], before["created_at"])
        self.assertEqual(goal["goal_id"], self.goal_id)
        self.assertEqual(len(goal["history"]), len(before["history"]) + 1)
        for field, value in patch.items():
            self.assertEqual(goal[field], value)

    def test_persistence_replace_failure_preserves_previous_goal(self):
        before = copy.deepcopy(self.store.goals)
        disk = self.path.read_bytes()
        with patch("task_coordinator_service.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                self.store.update(self.goal_id, {"intent": "Changed"})
        self.assertEqual(self.store.goals, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def test_invalid_goal_fields_rejected(self):
        for intent, skills, priority in (("", ["memory.query"], "medium"),
                                        ("Work", "memory.query", "medium"),
                                        ("Work", [""], "medium"),
                                        ("Work", [], "medium"),
                                        ("Work", ["memory.query"], "urgent")):
            with self.subTest(intent=intent, skills=skills, priority=priority):
                before = copy.deepcopy(self.store.goals)
                with self.assertRaises((ValueError, TypeError)):
                    self.store.create(intent, skills, priority)
                self.assertEqual(self.store.goals, before)

    def test_caller_metadata_mutation_cannot_rewrite_committed_history(self):
        update_patch = {"intent": "Changed", "extra": {"nested": ["original"]}}
        self.store.update(self.goal_id, update_patch)
        metadata = {"result": {"items": ["original"]}}
        self.store.transition(self.goal_id, "completed", **metadata)
        before = copy.deepcopy(self.store.goals)
        disk = self.path.read_bytes()
        update_patch["extra"]["nested"].append("rewritten")
        metadata["result"]["items"].append("rewritten")
        self.assertEqual(self.store.goals, before)
        self.assertEqual(self.path.read_bytes(), disk)

    def test_restart_recovers_only_inflight_goals(self):
        originals = {}
        for target in ("created", "broadcast", "assigned", "executing", "completed", "failed", "suspended"):
            goal_id = self.store.create("Work", ["memory.query"])["goal_id"]
            if target in ("broadcast", "assigned", "executing"):
                for state in ("broadcast", "assigned", "executing"):
                    self.store.transition(goal_id, state)
                    if state == target:
                        break
            elif target != "created":
                self.store.transition(goal_id, target)
            originals[goal_id] = copy.deepcopy(self.store.get(goal_id))
        restored = GoalStore(str(self.path))
        restored.load()
        restored.recover_inflight()
        for goal_id, original in originals.items():
            recovered = restored.get(goal_id)
            with self.subTest(state=original["state"]):
                if original["state"] in ("broadcast", "assigned", "executing"):
                    self.assertEqual(recovered["state"], "failed")
                    self.assertEqual(recovered["history"][:-1], original["history"])
                    self.assertEqual(recovered["history"][-1]["metadata"]["reason"], "coordinator_restart")
                else:
                    self.assertEqual(recovered, original)
        reloaded = GoalStore(str(self.path))
        reloaded.load()
        self.assertEqual(reloaded.goals, restored.goals)
        before = copy.deepcopy(restored.goals)
        restored.recover_inflight()
        self.assertEqual(restored.goals, before)


class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_auction_never_publishes_assignment(self):
        import time
        from request_budget import request_deadline
        respond = AsyncMock()
        token = request_deadline.set(time.time() + .01)
        try:
            await self.coordinator.handle_goal({"payload": {"intent": "Work",
                "required_skills": ["memory.query"], "proposal_window_ms": 30}, "respond": respond})
        finally:
            request_deadline.reset(token)
        result = respond.call_args.args[0]
        self.assertFalse(result["ok"])
        self.assertEqual(result["goal"]["state"], "failed")
        self.assertEqual([call.args[0] for call in self.coordinator.fabric.publish.call_args_list],
                         ["goal.broadcast"])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.coordinator = TaskCoordinator.__new__(TaskCoordinator)
        self.coordinator.goals = GoalStore(str(Path(self.temp.name) / "goals.json"))
        self.coordinator.reflections = ReflectionStore(str(Path(self.temp.name) / "reflection.json"))
        self.coordinator.fabric = AsyncMock()

    async def test_invalid_update_returns_error_and_preserves_goal(self):
        goal_id = self.coordinator.goals.create("Work", ["memory.query"])["goal_id"]
        before = copy.deepcopy(self.coordinator.goals.get(goal_id))
        respond = AsyncMock()
        await self.coordinator.handle_goal_update({"payload": {"goal_id": goal_id,
            "patch": {"intent": "Changed", "state": "invented"}}, "respond": respond})
        self.assertFalse(respond.call_args.args[0]["ok"])
        self.assertEqual(self.coordinator.goals.get(goal_id), before)

    async def test_invalid_create_returns_error(self):
        respond = AsyncMock()
        await self.coordinator.handle_goal_create({"payload": {"intent": "Work",
            "required_skills": "memory.query"}, "respond": respond})
        self.assertFalse(respond.call_args.args[0]["ok"])
        self.assertEqual(self.coordinator.goals.goals, {})

    async def test_submit_transport_failure_persists_queryable_failed_goal(self):
        goal_id = self.coordinator.goals.create("Work", ["memory.query"])["goal_id"]
        self.coordinator.fabric.publish.side_effect = RuntimeError("transport unavailable")
        respond = AsyncMock()
        await self.coordinator.handle_goal({"payload": {"goal_id": goal_id,
            "proposal_window_ms": 0}, "respond": respond})
        self.assertFalse(respond.call_args.args[0]["ok"])
        self.assertIn("transport unavailable", respond.call_args.args[0]["error"])
        status_response = AsyncMock()
        await self.coordinator.handle_goal_status({"payload": {"goal_id": goal_id},
            "respond": status_response})
        self.assertEqual(status_response.call_args.args[0]["goal"]["state"], "failed")
        restored = GoalStore(str(self.coordinator.goals.path))
        restored.load()
        self.assertEqual(restored.get(goal_id)["state"], "failed")

    async def test_no_proposals_results_in_failed_goal(self):
        respond = AsyncMock()
        await self.coordinator.handle_goal({"payload": {"intent": "Work",
            "required_skills": ["memory.query"], "proposal_window_ms": 0}, "respond": respond})
        result = respond.call_args.args[0]
        self.assertFalse(result["ok"])
        self.assertEqual(result["goal"]["state"], "failed")
        self.assertEqual(result["unassigned_skills"], ["memory.query"])

    async def test_unsubscribe_failure_still_returns_persisted_failed_goal(self):
        subscription = AsyncMock()
        subscription.unsubscribe.side_effect = RuntimeError("cleanup failed")
        self.coordinator.fabric.subscribe_async.return_value = subscription
        respond = AsyncMock()
        await self.coordinator.handle_goal({"payload": {"intent": "Work",
            "required_skills": ["memory.query"], "proposal_window_ms": 0}, "respond": respond})
        respond.assert_awaited_once()
        result = respond.call_args.args[0]
        self.assertFalse(result["ok"])
        self.assertIn("cleanup failed", result["error"])
        self.assertEqual(result["goal"]["state"], "failed")
        restored = GoalStore(str(self.coordinator.goals.path))
        restored.load()
        self.assertEqual(restored.get(result["goal"]["goal_id"])["state"], "failed")

    async def test_terminal_update_during_submission_still_returns_error(self):
        goal_id = self.coordinator.goals.create("Work", ["memory.query"])["goal_id"]
        subscription = AsyncMock()
        async def subscribe(*args):
            self.coordinator.goals.transition(goal_id, "failed", error="external failure")
            return subscription
        self.coordinator.fabric.subscribe_async.side_effect = subscribe
        respond = AsyncMock()
        await self.coordinator.handle_goal({"payload": {"goal_id": goal_id,
            "proposal_window_ms": 0}, "respond": respond})
        respond.assert_awaited_once()
        self.assertFalse(respond.call_args.args[0]["ok"])
        goal = self.coordinator.goals.get(goal_id)
        self.assertEqual(goal["state"], "failed")
        self.assertEqual([event["state"] for event in goal["history"]],
                         ["created", "broadcast", "failed"])

    def test_reflection_save_failure_preserves_memory_and_disk(self):
        reflections = self.coordinator.reflections
        execution = [{"skill": "memory.query", "ok": True}]
        reflections.record_execution("first", execution)
        before = copy.deepcopy(reflections.skills)
        disk = reflections.path.read_bytes()
        with patch("task_coordinator_service.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaises(OSError):
                reflections.record_execution("second", execution)
        self.assertEqual(reflections.skills, before)
        self.assertEqual(reflections.path.read_bytes(), disk)

    async def test_duplicate_submission_executes_and_broadcasts_once(self):
        goal_id = self.coordinator.goals.create("Work", ["memory.query"])["goal_id"]
        subscribed = asyncio.Event()
        release = asyncio.Event()
        subscription = AsyncMock()
        async def subscribe(subject, callback):
            subscribed.set()
            await release.wait()
            callback({"payload": {"goal_id": goal_id, "node_id": "node-a",
                                  "skills_offered": ["memory.query"], "confidence": 0.9}})
            return subscription
        self.coordinator.fabric.subscribe_async.side_effect = subscribe
        self.coordinator.execute_assignments = AsyncMock(return_value=[{"skill": "memory.query", "ok": True}])
        first_response, duplicate_response = AsyncMock(), AsyncMock()
        message = {"payload": {"goal_id": goal_id, "proposal_window_ms": 0}}
        first = asyncio.create_task(self.coordinator.handle_goal({**message, "respond": first_response}))
        try:
            await asyncio.wait_for(subscribed.wait(), timeout=2)
            await self.coordinator.handle_goal({**message, "respond": duplicate_response})
        finally:
            release.set()
            await first
        self.assertFalse(duplicate_response.call_args.args[0]["ok"])
        self.assertTrue(first_response.call_args.args[0]["ok"])
        self.coordinator.execute_assignments.assert_awaited_once()
        broadcasts = [call for call in self.coordinator.fabric.publish.await_args_list
                      if call.args[0] == "goal.broadcast"]
        self.assertEqual(len(broadcasts), 1)
        before = copy.deepcopy(self.coordinator.goals.get(goal_id))
        await self.coordinator.handle_goal({**message, "respond": duplicate_response})
        self.assertEqual(self.coordinator.goals.get(goal_id), before)
        self.coordinator.execute_assignments.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
