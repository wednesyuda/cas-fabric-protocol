"""
Runtime canary for Milestone 5 Goal System.

Passes only if a goal can be created, inspected, submitted through the
Task Auction path, and observed as completed with lifecycle history.
"""

from __future__ import annotations

import asyncio
import json
import time

from fabric_nats import NATSFabric


TOKEN = f"CAS_M5_CANARY_{int(time.time())}"


def fail(label: str, payload: object) -> int:
    print("FAIL " + label + "=" + json.dumps(payload, sort_keys=True))
    return 1


async def main() -> int:
    fabric = NATSFabric()
    await fabric.connect(connect_timeout=5.0)

    write = await fabric.request(
        "memory.write",
        {
            "content": f"{TOKEN}: Goal System canary memory.",
            "memory_type": "semantic",
            "source": "verify_milestone5_runtime",
            "metadata": {"milestone": 5, "token": TOKEN},
        },
        timeout=30,
    )
    if not write or not write.get("ok"):
        await fabric.close()
        return fail("setup_memory.write", write)

    created = await fabric.request(
        "goal.create",
        {
            "intent": f"What does Goal System canary {TOKEN} prove?",
            "required_skills": ["memory.query", "reasoning.llm"],
            "priority": "high",
        },
        timeout=30,
    )
    if not created or not created.get("ok"):
        await fabric.close()
        return fail("goal.create", created)
    goal_id = created["goal"]["goal_id"]
    if created["goal"].get("state") != "created":
        await fabric.close()
        return fail("goal_created_state", created)

    initial_status = await fabric.request("goal.status", {"goal_id": goal_id}, timeout=30)
    if not initial_status or not initial_status.get("ok") or initial_status["goal"].get("state") != "created":
        await fabric.close()
        return fail("goal.status.initial", initial_status)

    submitted = await fabric.request(
        "goal.submit",
        {"goal_id": goal_id, "proposal_window_ms": 1000},
        timeout=240,
    )
    if not submitted or not submitted.get("ok"):
        await fabric.close()
        return fail("goal.submit", submitted)

    final_status = await fabric.request("goal.status", {"goal_id": goal_id}, timeout=30)
    if not final_status or not final_status.get("ok"):
        await fabric.close()
        return fail("goal.status.final", final_status)
    goal = final_status["goal"]
    history_states = [event.get("state") for event in goal.get("history", [])]
    required_states = ["created", "broadcast", "assigned", "executing", "completed"]
    if goal.get("state") != "completed":
        await fabric.close()
        return fail("goal_not_completed", final_status)
    if not all(state in history_states for state in required_states):
        await fabric.close()
        return fail("goal_lifecycle_incomplete", final_status)

    print(
        "PASS milestone5="
        + json.dumps(
            {
                "token": TOKEN,
                "goal_id": goal_id,
                "state": goal.get("state"),
                "history_states": history_states,
                "proposal_count": submitted.get("proposal_count"),
                "assignment_count": len(submitted.get("assignments", [])),
                "execution_ok": all(item.get("ok") for item in submitted.get("execution", [])),
            },
            sort_keys=True,
        )
    )
    await fabric.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
