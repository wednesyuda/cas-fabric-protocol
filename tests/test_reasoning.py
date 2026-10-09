import asyncio
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference" / "python"))
from reasoning_node_service import ReasoningNode


def prepared(intent="Summarize"):
    return {"intent": intent, "values_signature": {"values_consulted": True},
            "prepared_context": {"relevant_semantic": []}}


class ReasoningTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_io_does_not_block_health_event_loop(self):
        node = ReasoningNode()
        respond = AsyncMock()
        entered = asyncio.Event()

        def slow_model(prompt):
            time.sleep(0.12)
            return "answer"

        async def heartbeat():
            await asyncio.sleep(0.02)
            entered.set()

        with patch("reasoning_node_service.ollama_generate", slow_model):
            beat = asyncio.create_task(heartbeat())
            request = asyncio.create_task(node.handle_reasoning({"payload": {
                "intent": "Summarize", "reasoning_request": prepared()}, "respond": respond}))
            await asyncio.sleep(0.06)
            self.assertTrue(entered.is_set())
            self.assertFalse(request.done(), "model I/O must allow other node work")
            await request
            await beat
        self.assertTrue(respond.call_args.args[0]["ok"])

    async def test_empty_model_output_is_failure(self):
        respond = AsyncMock()
        with patch("reasoning_node_service.ollama_generate", return_value=""):
            await ReasoningNode().handle_reasoning({"payload": {
                "intent": "Summarize", "reasoning_request": prepared()}, "respond": respond})
        self.assertFalse(respond.call_args.args[0]["ok"])

    async def test_prepared_intent_cannot_be_swapped(self):
        respond = AsyncMock()
        with patch("reasoning_node_service.ollama_generate", return_value="answer") as model:
            await ReasoningNode().handle_reasoning({"payload": {
                "intent": "Different intent", "reasoning_request": prepared()}, "respond": respond})
        self.assertFalse(respond.call_args.args[0]["ok"])
        model.assert_not_called()

    async def test_values_missing_rejected_before_model(self):
        respond = AsyncMock()
        with patch("reasoning_node_service.ollama_generate") as model:
            await ReasoningNode().handle_reasoning({"payload": {
                "intent": "Summarize", "reasoning_request": {"prepared_context": {}}}, "respond": respond})
        self.assertFalse(respond.call_args.args[0]["ok"])
        model.assert_not_called()
