"""
Milestone 1 Canonical Context Preparation Node.

Implements RFC-003 Interface A by exposing:
  - reasoning.prepare_context

It returns a reasoning.request envelope with prepared_context,
values_signature, risk_assessment, and constraints.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import uuid

from fabric_nats import NATSFabric


LOGGER = logging.getLogger("cas_fabric.context_preparation")


class ContextPreparationNode:
    def __init__(self) -> None:
        self.fabric = NATSFabric()

    async def start(self) -> None:
        await self.fabric.connect()
        await self.fabric.subscribe_async("capability.reasoning.prepare_context", self.handle_prepare)
        LOGGER.info("Context preparation node ready: capability=reasoning.prepare_context")

    async def handle_prepare(self, message: dict) -> None:
        respond = message.get("respond")
        payload = message.get("payload", {})
        try:
            intent = str(payload["intent"]).strip()
            if not intent:
                raise ValueError("intent must not be empty")

            memory = await self.fabric.request(
                "memory.query",
                {"query": intent, "limit": int(payload.get("memory_limit", 5))},
                timeout=30,
            )
            if not memory or not memory.get("ok"):
                raise RuntimeError(f"memory.query failed: {memory}")

            semantic = []
            for item in memory.get("results", []):
                semantic.append(
                    {
                        "content": item.get("content"),
                        "score": item.get("score"),
                        "source": item.get("source"),
                        "memory_type": item.get("memory_type", "semantic"),
                        "metadata": item.get("metadata", {}),
                    }
                )

            envelope = {
                "type": "reasoning.request",
                "request_id": str(uuid.uuid4()),
                "originating_node": str(payload.get("originating_node", "context-preparation-node")),
                "intent": intent,
                "prepared_context": {
                    "working_memory": [],
                    "relevant_episodic": [],
                    "relevant_semantic": semantic,
                    "active_goal": payload.get("active_goal"),
                },
                "values_signature": {
                    "values_consulted": True,
                    "tension_detected": False,
                    "ethical_alignment_score": 0.5,
                },
                "risk_assessment": {
                    "risk_flags": [],
                    "confidence_floor": 0.98,
                    "recommended_caution": None,
                },
                "constraints": {
                    "max_tokens": int(payload.get("max_tokens", 1000)),
                    "timeout_ms": int(payload.get("timeout_ms", 5000)),
                    "confidence_threshold": float(payload.get("confidence_threshold", 0.98)),
                },
            }
            result = {"ok": True, "reasoning_request": envelope}
        except Exception as exc:
            LOGGER.exception("reasoning.prepare_context failed")
            result = {"ok": False, "error": str(exc)}

        if respond:
            await respond(result)

    async def close(self) -> None:
        await self.fabric.close()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    node = ContextPreparationNode()
    await node.start()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()
    await node.close()


if __name__ == "__main__":
    asyncio.run(main())
