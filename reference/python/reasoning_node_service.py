"""
Milestone 1 Reasoning Node.

Exposes one NATS capability:
  - reasoning.llm

The node queries Memory Node for context and calls Ollama for a response.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import urllib.request

from fabric_nats import NATSFabric


LOGGER = logging.getLogger("cas_fabric.reasoning_node")

OLLAMA_URL = os.getenv("CAS_OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("CAS_REASONING_MODEL", "local-reasoning-model")


def ollama_generate(prompt: str) -> str:
    data = json.dumps(
        {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 256,
            },
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return str(payload.get("response", "")).strip()


class ReasoningNode:
    def __init__(self) -> None:
        self.fabric = NATSFabric()

    async def start(self) -> None:
        await self.fabric.connect()
        await self.fabric.subscribe_async("capability.reasoning.llm", self.handle_reasoning)
        LOGGER.info("Reasoning node ready: model=%s", MODEL)

    async def handle_reasoning(self, message: dict) -> None:
        respond = message.get("respond")
        payload = message.get("payload", {})
        try:
            intent = str(payload["intent"]).strip()
            if not intent:
                raise ValueError("intent must not be empty")

            prepared = payload.get("reasoning_request")
            if not prepared:
                prepared_response = await self.fabric.request(
                    "reasoning.prepare_context",
                    {
                        "intent": intent,
                        "memory_limit": int(payload.get("memory_limit", 3)),
                        "originating_node": "reasoning-node",
                    },
                    timeout=45,
                )
                if not prepared_response or not prepared_response.get("ok"):
                    raise RuntimeError(f"reasoning.prepare_context failed: {prepared_response}")
                prepared = prepared_response.get("reasoning_request")

            if not prepared or not prepared.get("values_signature", {}).get("values_consulted"):
                raise RuntimeError("reasoning.request missing values_signature")

            prepared_context = prepared.get("prepared_context", {})
            relevant_semantic = prepared_context.get("relevant_semantic", [])
            context_lines = []
            for item in relevant_semantic:
                content = item.get("content")
                if content:
                    context_lines.append(f"- {content}")
            context = "\n".join(context_lines) if context_lines else "- No relevant memory found."

            prompt = (
                "You are a CAS Fabric Milestone 1 reasoning node.\n"
                "You received an RFC-003 reasoning.request envelope prepared by the Memory Fabric path.\n"
                "Answer using the prepared context. Be concise.\n\n"
                f"Memory context:\n{context}\n\n"
                f"Intent:\n{intent}\n\n"
                "Answer:"
            )
            output = ollama_generate(prompt)
            result = {
                "ok": True,
                "model": MODEL,
                "output": output,
                "reasoning_request": prepared,
                "memory_results": relevant_semantic,
            }
        except Exception as exc:
            LOGGER.exception("reasoning.llm failed")
            result = {"ok": False, "error": str(exc), "output": "", "memory_results": []}

        if respond:
            await respond(result)

    async def close(self) -> None:
        await self.fabric.close()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    node = ReasoningNode()
    await node.start()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()
    await node.close()


if __name__ == "__main__":
    asyncio.run(main())
