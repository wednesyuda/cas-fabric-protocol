import asyncio
import json
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference/python"))
from fabric_nats import NATSFabric


class BudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_queued_request_never_runs_and_overload_is_fast(self):
        fabric = NATSFabric()
        fabric._nc = SimpleNamespace(subscribe=AsyncMock())
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []
        async def handler(message):
            calls.append(message["payload"]["id"])
            entered.set()
            await release.wait()
        await fabric.subscribe_async("capability.probe", handler, max_active=1, max_queued=1, max_queue_wait=1)
        cb = fabric._nc.subscribe.call_args.kwargs["cb"]
        replies = []
        def msg(i, budget):
            async def respond(data): replies.append((i, json.loads(data)))
            return SimpleNamespace(data=json.dumps({"id": i,"expires_at_ms":(time.time()+budget)*1000}).encode(), reply="inbox", respond=respond)
        await cb(msg(1, 1)); await entered.wait()
        await cb(msg(2, .02))
        await cb(msg(3, 1))
        self.assertEqual(replies[-1][1]["code"], "busy")
        await asyncio.sleep(.04)
        release.set()
        await asyncio.gather(*list(fabric._dispatch_tasks))
        self.assertEqual(calls, [1])
        self.assertTrue(any(r[1].get("code") == "expired" for r in replies))

    async def test_outgoing_budget_does_not_extend_parent(self):
        from request_budget import request_deadline
        fabric = NATSFabric(); fabric._nc = SimpleNamespace(request=AsyncMock(return_value=SimpleNamespace(data=b'{"ok":true}')))
        token = request_deadline.set(time.time()+.5)
        try:
            await fabric.request("probe", {}, timeout=20)
            args=fabric._nc.request.call_args
            self.assertLessEqual(args.kwargs["timeout"], .5)
            self.assertLessEqual(json.loads(args.args[1])["expires_at_ms"], request_deadline.get()*1000)
        finally: request_deadline.reset(token)

    async def test_timed_out_provider_keeps_slot_until_io_finishes(self):
        import threading
        from unittest.mock import patch
        from reasoning_node_service import ReasoningNode
        from request_budget import request_deadline
        started, release = threading.Event(), threading.Event()
        calls = []
        def model(prompt):
            calls.append(prompt); started.set(); release.wait(3); return "answer"
        node = ReasoningNode(); node.fabric._nc = SimpleNamespace(subscribe=AsyncMock())
        replies = []
        def message(i, ttl):
            async def respond(data): replies.append(json.loads(data))
            intent = "intent " + str(i)
            payload = {"intent": intent, "expires_at_ms": (time.time()+ttl)*1000,
                       "reasoning_request": {"intent": intent,"values_signature":{"values_consulted":True},"prepared_context":{}}}
            return SimpleNamespace(data=json.dumps(payload).encode(), reply="reply", respond=respond)
        await node.fabric.subscribe_async("probe",node.handle_reasoning,max_active=1,max_queued=0)
        cb=node.fabric._nc.subscribe.call_args.kwargs["cb"]
        with patch("reasoning_node_service.ollama_generate",model):
            await cb(message(1,.03))
            for _ in range(50):
                if started.is_set(): break
                await asyncio.sleep(.005)
            self.assertTrue(started.is_set())
            await asyncio.sleep(.04)
            await cb(message(2,1))
            self.assertEqual(replies[-1]["code"],"busy")
            self.assertEqual(len(calls),1)
            release.set()
            await asyncio.gather(*list(node.fabric._dispatch_tasks))
        self.assertFalse(replies[-1]["ok"])
        self.assertEqual(node.fabric.admission_metrics["probe"]["inflight"],0)

    async def test_embedding_expiry_prevents_new_persistent_write(self):
        from memory_fabric import MemoryFabric,MemoryType
        from request_budget import request_deadline
        memory=MemoryFabric.__new__(MemoryFabric)
        memory.node_id="probe";memory.collections={MemoryType.SEMANTIC:"semantic"}
        memory.qdrant=SimpleNamespace(upsert_memory=AsyncMock())
        async def embed(text):
            await asyncio.sleep(.03)
            return [1.0]
        memory.embedding_fn=embed
        token=request_deadline.set(time.time()+.01)
        try:
            with self.assertRaises(TimeoutError):
                await memory.write_memory(MemoryType.SEMANTIC,"text","probe")
            memory.qdrant.upsert_memory.assert_not_called()
        finally:request_deadline.reset(token)
