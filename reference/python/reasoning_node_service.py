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
from request_budget import remaining
from document_answer import RULE, answer_schema, evidence_for, validate_answer


LOGGER = logging.getLogger("cas_fabric.reasoning_node")

OLLAMA_URL = os.getenv("CAS_OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("CAS_REASONING_MODEL", "local-reasoning-model")


def document_generate(evidence, intent):
    payload = {"model": MODEL, "stream": False, "think": False, "format": answer_schema(evidence),
               "messages": [{"role": "system", "content": RULE},
                            {"role": "user", "content": json.dumps({"documents": evidence, "question": intent}, ensure_ascii=False)}],
               "options": {"temperature": 0, "seed": 42, "num_predict": 384, "num_ctx": 4096}}
    req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=remaining(120)) as response:
        result = json.load(response)
    return result.get("message", {}).get("content", "")


def ollama_generate(prompt: str) -> str:
    timeout = remaining(120)
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
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return str(payload.get("response", "")).strip()


class ReasoningNode:
    def __init__(self) -> None:
        self.fabric = NATSFabric()
        self.document_mode = os.getenv("CAS_DOCUMENT_QA", "0") == "1"

    async def start(self) -> None:
        await self.fabric.connect()
        await self.fabric.subscribe_async("capability.reasoning.llm", self.handle_reasoning, max_active=1, max_queued=2, max_queue_wait=15)
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
            if prepared.get("intent") != intent:
                raise ValueError("reasoning.request intent does not match request intent")

            prepared_context = prepared.get("prepared_context", {})
            relevant_semantic = prepared_context.get("relevant_semantic", [])
            if self.document_mode:
                evidence = evidence_for(relevant_semantic)
                if prepared.get("constraints", {}).get("requires_human_review"):
                    answer = {"answer": "Permintaan memerlukan tinjauan manusia.", "sources": [], "abstain": True}
                    status = "needs_review"
                elif not evidence:
                    answer = {"answer": "Informasi tidak tersedia dalam dokumen.", "sources": [], "abstain": True}
                    status = "abstain"
                else:
                    raw = await asyncio.to_thread(document_generate, evidence, intent)
                    remaining()
                    answer = validate_answer(raw, evidence)
                    status = "needs_review" if answer.get("needs_review") else "abstain" if answer["abstain"] else "answer"
                result = {"ok": True, "type": "reasoning.response", "request_id": prepared.get("request_id"),
                          "model": MODEL, "status": status, "output": answer["answer"],
                          "sources": answer["sources"], "evidence": evidence, "reasoning_request": prepared,
                          "memory_results": relevant_semantic, "actions_allowed": False}
                if respond:
                    await respond(result)
                return
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
            remaining()
            output = await asyncio.to_thread(ollama_generate, prompt)
            remaining()
            if not output:
                raise RuntimeError("model returned empty output")
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
