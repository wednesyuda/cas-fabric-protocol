"""
Runtime canary for Milestone 2 Task Auction.

Passes only if goal.submit produces proposals, assignments, and an
execution result through real NATS.
"""

from __future__ import annotations

import asyncio
import json
import time

from fabric_nats import NATSFabric


TOKEN = f"CAS_M2_CANARY_{int(time.time())}"
CONTENT = f"{TOKEN}: Milestone 2 proves goal broadcast, proposals, assignments, and execution through Task Auction."


async def main() -> int:
    fabric = NATSFabric()
    await fabric.connect(connect_timeout=5.0)

    write = await fabric.request(
        "memory.write",
        {
            "content": CONTENT,
            "memory_type": "semantic",
            "source": "verify_milestone2_runtime",
            "metadata": {"milestone": 2, "token": TOKEN},
        },
        timeout=30,
    )
    if not write or not write.get("ok"):
        print("FAIL setup_memory.write=" + json.dumps(write, sort_keys=True))
        await fabric.close()
        return 1

    goal = await fabric.request(
        "goal.submit",
        {
            "intent": f"What did Task Auction canary {TOKEN} prove?",
            "required_skills": ["memory.query", "reasoning.llm"],
            "priority": "high",
            "proposal_window_ms": 1000,
        },
        timeout=240,
    )
    if not goal or not goal.get("ok"):
        print("FAIL goal.submit=" + json.dumps(goal, sort_keys=True))
        await fabric.close()
        return 1
    if goal.get("type") != "goal.result":
        print("FAIL missing_goal_result_envelope=" + json.dumps(goal, sort_keys=True))
        await fabric.close()
        return 1
    if goal.get("unassigned_skills"):
        print("FAIL unassigned_skills=" + json.dumps(goal, sort_keys=True))
        await fabric.close()
        return 1

    assigned_skills = {
        skill
        for assignment in goal.get("assignments", [])
        for skill in assignment.get("skills_assigned", [])
    }
    required = {"memory.query", "reasoning.llm"}
    if not required.issubset(assigned_skills):
        print("FAIL missing_assignments=" + json.dumps(goal, sort_keys=True))
        await fabric.close()
        return 1
    if goal.get("valid_proposal_count", 0) < 2:
        print("FAIL insufficient_valid_proposals=" + json.dumps(goal, sort_keys=True))
        await fabric.close()
        return 1

    execution = goal.get("execution", [])
    failed_execution = [item for item in execution if not item.get("ok")]
    if failed_execution:
        print("FAIL assignment_execution=" + json.dumps(failed_execution, sort_keys=True))
        await fabric.close()
        return 1
    reasoning = next((item for item in execution if item.get("skill") == "reasoning.llm"), None)
    output = ((reasoning or {}).get("response") or {}).get("output", "")
    if not output:
        print("FAIL missing_reasoning_output=" + json.dumps(goal, sort_keys=True))
        await fabric.close()
        return 1

    print(
        "PASS milestone2="
        + json.dumps(
            {
                "token": TOKEN,
                "goal_id": goal.get("goal_id"),
                "proposal_count": goal.get("proposal_count"),
                "valid_proposal_count": goal.get("valid_proposal_count"),
                "assignment_count": len(goal.get("assignments", [])),
                "assigned_skills": sorted(assigned_skills),
                "execution_ok": all(item.get("ok") for item in execution),
                "reasoning_output": output[:500],
            },
            sort_keys=True,
        )
    )
    await fabric.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
