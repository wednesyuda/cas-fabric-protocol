import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference" / "python"))
from auction_worker_node_service import AuctionWorker
from task_coordinator_service import TaskCoordinator


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_selected_worker_route_is_used_and_result_verified(self):
        coordinator = TaskCoordinator.__new__(TaskCoordinator)
        coordinator.fabric = AsyncMock()
        assignment = {"goal_id": "goal-a", "node_id": "winner", "skills_assigned": ["memory.query"],
                      "execution_capability": "auction.execute.winner"}

        async def request(capability, payload, **kwargs):
            if capability != "auction.execute.winner":
                return {"ok": True, "output": "loser output"}
            return {"ok": True, "node_id": "winner", "goal_id": "goal-a", "skill": "memory.query",
                    "response": {"ok": True, "output": "winner output"}}

        coordinator.fabric.request.side_effect = request
        result = await coordinator.execute_assignments("Intent A", [assignment])
        self.assertTrue(result[0]["ok"])
        self.assertEqual(result[0]["response"]["output"], "winner output")
        self.assertEqual(coordinator.fabric.request.call_args.args[0], "auction.execute.winner")

    async def test_wrong_responder_identity_is_failure(self):
        for field, wrong in (("node_id", "loser"), ("goal_id", "different"), ("skill", "other")):
            with self.subTest(field=field):
                coordinator = TaskCoordinator.__new__(TaskCoordinator)
                coordinator.fabric = AsyncMock()
                response = {"ok": True, "node_id": "winner", "goal_id": "goal-a", "skill": "memory.query",
                            "response": {"ok": True}}
                response[field] = wrong
                coordinator.fabric.request.return_value = response
                result = await coordinator.execute_assignments("Intent A", [{"goal_id": "goal-a",
                    "node_id": "winner", "skills_assigned": ["memory.query"],
                    "execution_capability": "auction.execute.winner"}])
                self.assertFalse(result[0]["ok"])

    async def test_missing_worker_route_fails_without_generic_execution(self):
        coordinator = TaskCoordinator.__new__(TaskCoordinator)
        coordinator.fabric = AsyncMock(return_value={"ok": True})
        result = await coordinator.execute_assignments("Intent A", [{"goal_id": "goal-a",
            "node_id": "winner", "skills_assigned": ["memory.query"]}])
        self.assertFalse(result[0]["ok"])
        coordinator.fabric.request.assert_not_awaited()


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    def worker(self):
        worker = AuctionWorker()
        worker.node_id = "winner"
        worker.skills = ["memory.query"]
        worker.fabric = AsyncMock()
        worker.execute_skill = AsyncMock(return_value={"ok": True, "output": "winner output"})
        return worker

    async def assign(self, worker):
        await worker.handle_assignment({"payload": {"goal_id": "goal-a", "intent": "Intent A",
            "assignment": {"node_id": "winner", "skills_assigned": ["memory.query"],
                           "execution_capability": worker.execution_capability}}})

    async def execute(self, worker, **overrides):
        respond = AsyncMock()
        await worker.handle_execute({"payload": {"goal_id": "goal-a", "node_id": "winner",
            "skill": "memory.query", "intent": "Intent A", **overrides}, "respond": respond})
        return respond.call_args.args[0]

    async def test_worker_executes_only_recorded_assignment(self):
        worker = self.worker()
        missing = await self.execute(worker)
        self.assertFalse(missing["ok"])
        worker.execute_skill.assert_not_awaited()
        await self.assign(worker)
        result = await self.execute(worker)
        self.assertTrue(result["ok"])
        self.assertEqual(result["node_id"], "winner")
        self.assertEqual(result["response"]["output"], "winner output")
        worker.execute_skill.assert_awaited_once_with("memory.query", "Intent A")
        self.assertFalse((await self.execute(worker))["ok"])
        worker.execute_skill.assert_awaited_once()

    async def test_worker_rejects_wrong_intent_skill_or_node(self):
        for invalid in ({"intent": "Intent B"}, {"skill": "reasoning.llm"}, {"node_id": "loser"}):
            worker = self.worker()
            await self.assign(worker)
            self.assertFalse((await self.execute(worker, **invalid))["ok"])
            worker.execute_skill.assert_not_awaited()

    async def test_worker_maps_failure_without_claiming_success(self):
        worker = self.worker()
        await self.assign(worker)
        worker.execute_skill.side_effect = RuntimeError("provider unavailable")
        result = await self.execute(worker)
        self.assertFalse(result["ok"])
        self.assertIn("provider unavailable", result["error"])

    async def test_full_worker_does_not_propose_new_work(self):
        worker = self.worker()
        for index in range(1024):
            worker.assignments[str(index)] = {"skills": ["memory.query"], "started": set(), "finished": set()}
        await worker.handle_goal({"payload": {"goal_id": "new", "required_skills": ["memory.query"],
                                               "proposal_subject": "goal.proposal.new"}})
        worker.fabric.publish.assert_not_awaited()
        worker.assignments["0"]["finished"].add("memory.query")
        await worker.handle_goal({"payload": {"goal_id": "new", "required_skills": ["memory.query"],
                                               "proposal_subject": "goal.proposal.new"}})
        worker.fabric.publish.assert_awaited_once()
