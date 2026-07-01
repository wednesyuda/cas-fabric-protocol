"""
Canonical Milestone 1 runtime canary.

Passes only if:
  1. memory.write succeeds
  2. reasoning.prepare_context returns an RFC-003 reasoning.request envelope
  3. reasoning.llm uses that prepared envelope and returns output
"""

from __future__ import annotations

import asyncio
import json
import time

from fabric_nats import NATSFabric


TOKEN = f"CAS_M1_CANONICAL_{int(time.time())}"
CONTENT = f"{TOKEN}: Canonical Milestone 1 proves RFC-002 memory plus RFC-003 Interface A context preparation."


def validate_reasoning_request(envelope: dict) -> list[str]:
    required_top = {
        "type",
        "request_id",
        "originating_node",
        "intent",
        "prepared_context",
        "values_signature",
        "risk_assessment",
        "constraints",
    }
    missing = sorted(required_top - set(envelope))
    ctx = envelope.get("prepared_context", {})
    for key in ["working_memory", "relevant_episodic", "relevant_semantic", "active_goal"]:
        if key not in ctx:
            missing.append(f"prepared_context.{key}")
    for key in ["values_consulted", "tension_detected", "ethical_alignment_score"]:
        if key not in envelope.get("values_signature", {}):
            missing.append(f"values_signature.{key}")
    for key in ["risk_flags", "confidence_floor", "recommended_caution"]:
        if key not in envelope.get("risk_assessment", {}):
            missing.append(f"risk_assessment.{key}")
    for key in ["max_tokens", "timeout_ms", "confidence_threshold"]:
        if key not in envelope.get("constraints", {}):
            missing.append(f"constraints.{key}")
    return missing


async def main() -> int:
    fabric = NATSFabric()
    await fabric.connect(connect_timeout=5.0)

    write = await fabric.request(
        "memory.write",
        {
            "content": CONTENT,
            "memory_type": "semantic",
            "source": "verify_milestone1_canonical_runtime",
            "metadata": {"milestone": "1-canonical", "token": TOKEN},
        },
        timeout=30,
    )
    if not write or not write.get("ok"):
        print("FAIL memory.write=" + json.dumps(write, sort_keys=True))
        await fabric.close()
        return 1

    prepared = await fabric.request(
        "reasoning.prepare_context",
        {"intent": f"What does {TOKEN} prove?", "memory_limit": 5},
        timeout=60,
    )
    envelope = (prepared or {}).get("reasoning_request", {})
    missing = validate_reasoning_request(envelope)
    if not prepared or not prepared.get("ok") or missing:
        print(
            "FAIL reasoning.prepare_context="
            + json.dumps({"response": prepared, "missing": missing}, sort_keys=True)
        )
        await fabric.close()
        return 1

    semantic = envelope.get("prepared_context", {}).get("relevant_semantic", [])
    if not any(TOKEN in str(item.get("content", "")) for item in semantic):
        print("FAIL prepared_context_missing_token=" + json.dumps(envelope, sort_keys=True))
        await fabric.close()
        return 1

    reasoning = await fabric.request(
        "reasoning.llm",
        {
            "intent": f"What does {TOKEN} prove?",
            "reasoning_request": envelope,
        },
        timeout=180,
    )
    if not reasoning or not reasoning.get("ok") or not reasoning.get("output"):
        print("FAIL reasoning.llm=" + json.dumps(reasoning, sort_keys=True))
        await fabric.close()
        return 1

    print(
        "PASS milestone1_canonical="
        + json.dumps(
            {
                "token": TOKEN,
                "memory_point_id": write.get("point_id"),
                "prepared_context_hits": len(semantic),
                "values_signature": envelope.get("values_signature"),
                "risk_assessment": envelope.get("risk_assessment"),
                "reasoning_model": reasoning.get("model"),
                "reasoning_output": reasoning.get("output")[:500],
            },
            sort_keys=True,
        )
    )
    await fabric.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
