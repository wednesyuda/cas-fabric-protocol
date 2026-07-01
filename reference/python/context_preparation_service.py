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
from dataclasses import dataclass

from fabric_nats import NATSFabric


LOGGER = logging.getLogger("cas_fabric.context_preparation")


@dataclass(frozen=True)
class ValuePolicy:
    value_id: str
    principle: str
    risk_terms: tuple[str, ...]
    weight: float
    suggested_reframe: str


VALUE_POLICIES = (
    ValuePolicy(
        value_id="privacy",
        principle="Protect private data and require consent before disclosure.",
        risk_terms=("private data", "personal data", "secret", "credential", "password", "token", "without consent"),
        weight=0.40,
        suggested_reframe="Ask for explicit consent and minimize private data exposure.",
    ),
    ValuePolicy(
        value_id="safety",
        principle="Avoid bypassing safeguards or enabling harmful action.",
        risk_terms=("bypass", "evade", "disable safety", "ignore policy", "unauthorized"),
        weight=0.35,
        suggested_reframe="Keep safeguards active and route risky action to review.",
    ),
    ValuePolicy(
        value_id="transparency",
        principle="Keep actions explainable and auditable.",
        risk_terms=("hide", "conceal", "undetectable", "no audit", "silent export"),
        weight=0.25,
        suggested_reframe="Make the action explicit, logged, and reviewable.",
    ),
)


def evaluate_values(intent: str) -> dict:
    lowered = intent.lower()
    matches = []
    for policy in VALUE_POLICIES:
        matched_terms = [term for term in policy.risk_terms if term in lowered]
        if matched_terms:
            matches.append(
                {
                    "value_id": policy.value_id,
                    "principle": policy.principle,
                    "matched_terms": matched_terms,
                    "weight": policy.weight,
                    "suggested_reframe": policy.suggested_reframe,
                }
            )

    tension_score = min(sum(item["weight"] for item in matches), 1.0)
    tension_detected = tension_score >= 0.35
    ethical_alignment_score = max(0.0, 1.0 - tension_score)
    risk_flags = [f"values_tension.{item['value_id']}" for item in matches]
    primary = matches[0] if matches else None

    return {
        "values_signature": {
            "values_consulted": True,
            "tension_detected": tension_detected,
            "ethical_alignment_score": round(ethical_alignment_score, 3),
            "values_applied": [policy.value_id for policy in VALUE_POLICIES],
        },
        "tension_signal": {
            "intent_summary": intent[:240],
            "conflicting_value": primary["principle"] if primary else None,
            "tension_score": round(tension_score, 3),
            "matched_values": matches,
            "suggested_reframe": primary["suggested_reframe"] if primary else None,
        } if tension_detected else None,
        "risk_assessment": {
            "risk_flags": risk_flags,
            "confidence_floor": 0.98,
            "recommended_caution": primary["suggested_reframe"] if primary else None,
        },
        "requires_human_review": tension_detected,
    }


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

            values = evaluate_values(intent)
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
                "values_signature": values["values_signature"],
                "tension_signal": values["tension_signal"],
                "risk_assessment": values["risk_assessment"],
                "constraints": {
                    "max_tokens": int(payload.get("max_tokens", 1000)),
                    "timeout_ms": int(payload.get("timeout_ms", 5000)),
                    "confidence_threshold": float(payload.get("confidence_threshold", 0.98)),
                    "requires_human_review": values["requires_human_review"],
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
