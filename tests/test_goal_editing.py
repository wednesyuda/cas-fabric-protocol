import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference" / "python"))
from task_coordinator_service import GoalStore, ReflectionStore, TaskCoordinator


class GoalEditingTests(unittest.TestCase):
    def test_execution_fields_locked_after_created(self):
        with tempfile.TemporaryDirectory() as temp:
            store = GoalStore(str(Path(temp) / "goals.json"))
            for target in ("broadcast", "assigned", "executing"):
                goal_id = store.create("Intent A", ["memory.query"])["goal_id"]
                for state in ("broadcast", "assigned", "executing"):
                    store.transition(goal_id, state)
                    if state == target:
                        break
                for field, value in (("intent", "Intent B"),
                                     ("required_skills", ["reasoning.llm"]), ("priority", "high")):
                    with self.subTest(state=target, field=field):
                        before = copy.deepcopy(store.goals)
                        disk = store.path.read_bytes()
                        with self.assertRaises(ValueError):
                            store.update(goal_id, {field: value})
                        self.assertEqual(store.goals, before)
                        self.assertEqual(store.path.read_bytes(), disk)


class SubmissionEditingTests(unittest.IsolatedAsyncioTestCase):
    async def test_auction_rejects_edit_and_executes_committed_intent(self):
        with tempfile.TemporaryDirectory() as temp:
            coordinator = TaskCoordinator.__new__(TaskCoordinator)
            coordinator.goals = GoalStore(str(Path(temp) / "goals.json"))
            coordinator.reflections = ReflectionStore(str(Path(temp) / "reflections.json"))
            coordinator.fabric = AsyncMock()
            coordinator.execute_assignments = AsyncMock(return_value=[{"skill": "memory.query", "ok": True}])
            goal_id = coordinator.goals.create("Intent A", ["memory.query"])["goal_id"]
            update_response = AsyncMock()

            async def subscribe(subject, callback):
                await coordinator.handle_goal_update({"payload": {"goal_id": goal_id,
                    "patch": {"intent": "Intent B"}}, "respond": update_response})
                callback({"payload": {"goal_id": goal_id, "node_id": "worker-a",
                    "skills_offered": ["memory.query"], "confidence": 0.99}})
                return AsyncMock()

            coordinator.fabric.subscribe_async.side_effect = subscribe
            response = AsyncMock()
            await coordinator.handle_goal({"payload": {"goal_id": goal_id,
                "proposal_window_ms": 0}, "respond": response})
            self.assertFalse(update_response.call_args.args[0]["ok"])
            self.assertTrue(response.call_args.args[0]["ok"])
            self.assertEqual(coordinator.execute_assignments.call_args.args[0], "Intent A")
            self.assertEqual(coordinator.goals.get(goal_id)["intent"], "Intent A")
            self.assertEqual(coordinator.goals.get(goal_id)["state"], "completed")
