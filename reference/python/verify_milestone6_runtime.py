"""
Runtime canary for Milestone 6 Reflection / Adaptive Scoring.

Passes only if execution creates reflection events, persists adaptive
confidence per skill, and exposes that confidence back through the
reflection status capability.
"""

from __future__ import annotations

import asyncio
import json
import time

from fabric_nats import NATSFabric


TOKEN = f"CAS_M6_CANARY_{int(time.time())}"
REQUIRED_SKILLS = {"memory.query", "reasoning.llm"}


def fail(label: str, payload: object) -> int:
    print("FAIL " + label + "=" + json.dumps(payload, sort_keys=True))
    return 1


async def reflection_status(fabric: NATSFabric, skill_id: str) -> dict:
    response = await fabric.request("reflection.status", {"skill_id": skill_id}, timeout=30)
    if not response or not response.get("ok"):
        raise RuntimeError(json.dumps(response, sort_keys=True))
    return response["reflection"]


async def main() -> int:
    fabric = NATSFabric()
    await fabric.connect(connect_timeout=5.0)

    before = {skill: await reflection_status(fabric, skill) for skill in REQUIRED_SKILLS}

    write = await fabric.request(
        "memory.write",
        {
            "content": f"{TOKEN}: Reflection and adaptive scoring canary memory.",
            "memory_type": "semantic",
            "source": "verify_milestone6_runtime",
            "metadata": {"milestone": 6, "token": TOKEN},
        },
        timeout=30,
    )
    if not write or not write.get("ok"):
        await fabric.close()
        return fail("setup_memory.write", write)

    goal = await fabric.request(
        "goal.submit",
        {
            "intent": f"What does Reflection canary {TOKEN} prove?",
            "required_skills": sorted(REQUIRED_SKILLS),
            "priority": "high",
            "proposal_window_ms": 1000,
        },
        timeout=240,
    )
    if not goal or not goal.get("ok"):
        await fabric.close()
        return fail("goal.submit", goal)

    reflection_events = goal.get("reflection_events", [])
    reflected_skills = {event.get("skill_id") for event in reflection_events}
    if not REQUIRED_SKILLS.issubset(reflected_skills):
        await fabric.close()
        return fail("missing_reflection_events", goal)

    after = {skill: await reflection_status(fabric, skill) for skill in REQUIRED_SKILLS}
    for skill in REQUIRED_SKILLS:
        if int(after[skill].get("attempt_count", 0)) <= int(before[skill].get("attempt_count", 0)):
            await fabric.close()
            return fail("reflection_attempt_not_incremented", {"before": before, "after": after})
        if after[skill].get("last_goal_id") != goal.get("goal_id"):
            await fabric.close()
            return fail("reflection_goal_not_recorded", {"goal": goal, "after": after})
        if float(after[skill].get("adaptive_confidence", 0.0)) < float(before[skill].get("adaptive_confidence", 0.0)):
            await fabric.close()
            return fail("adaptive_confidence_regressed", {"before": before, "after": after})

    proposal_scores = [
        proposal.get("adaptive_confidence")
        for proposal in goal.get("proposals", [])
        if proposal.get("adaptive_confidence") is not None
    ]
    if not proposal_scores:
        await fabric.close()
        return fail("missing_adaptive_proposal_scores", goal)

    print(
        "PASS milestone6="
        + json.dumps(
            {
                "token": TOKEN,
                "goal_id": goal.get("goal_id"),
                "reflection_event_count": len(reflection_events),
                "proposal_adaptive_scores": proposal_scores,
                "after": after,
            },
            sort_keys=True,
        )
    )
    await fabric.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
