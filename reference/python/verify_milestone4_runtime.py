"""
Runtime canary for Milestone 4 Skill Genome + Adaptive Plasticity.

Passes only if Task Auction proposals carry Skill Genome manifests,
assignments preserve those manifests, and execution produces retention
updates for the selected skills.
"""

from __future__ import annotations

import asyncio
import json
import time

from fabric_nats import NATSFabric


TOKEN = f"CAS_M4_CANARY_{int(time.time())}"


def fail(label: str, payload: object) -> int:
    print("FAIL " + label + "=" + json.dumps(payload, sort_keys=True))
    return 1


async def main() -> int:
    fabric = NATSFabric()
    await fabric.connect(connect_timeout=5.0)

    write = await fabric.request(
        "memory.write",
        {
            "content": f"{TOKEN}: Skill Genome and Adaptive Plasticity canary memory.",
            "memory_type": "semantic",
            "source": "verify_milestone4_runtime",
            "metadata": {"milestone": 4, "token": TOKEN},
        },
        timeout=30,
    )
    if not write or not write.get("ok"):
        await fabric.close()
        return fail("setup_memory.write", write)

    goal = await fabric.request(
        "goal.submit",
        {
            "intent": f"What does Skill Genome canary {TOKEN} prove?",
            "required_skills": ["memory.query", "reasoning.llm"],
            "priority": "high",
            "proposal_window_ms": 1000,
        },
        timeout=240,
    )
    if not goal or not goal.get("ok"):
        await fabric.close()
        return fail("goal.submit", goal)

    proposals = goal.get("proposals", [])
    assignments = goal.get("assignments", [])
    execution = goal.get("execution", [])
    proposal_manifests = [
        manifest
        for proposal in proposals
        for manifest in proposal.get("skill_manifests", [])
    ]
    assignment_manifests = [
        manifest
        for assignment in assignments
        for manifest in assignment.get("skill_manifests", [])
    ]
    retention_updates = [
        item.get("retention_update")
        for item in execution
        if item.get("retention_update")
    ]

    required = {"memory.query", "reasoning.llm"}
    proposed_skills = {manifest.get("skill_id") for manifest in proposal_manifests}
    assigned_skills = {
        skill
        for assignment in assignments
        for skill in assignment.get("skills_assigned", [])
    }
    retained_skills = {update.get("skill_id") for update in retention_updates}

    if not required.issubset(proposed_skills):
        await fabric.close()
        return fail("missing_proposal_manifests", goal)
    if not required.issubset(assigned_skills):
        await fabric.close()
        return fail("missing_assignment_skills", goal)
    if not required.issubset({manifest.get("skill_id") for manifest in assignment_manifests}):
        await fabric.close()
        return fail("missing_assignment_manifests", goal)
    if not required.issubset(retained_skills):
        await fabric.close()
        return fail("missing_retention_updates", goal)
    if any(update.get("lifecycle_recommendation") != "retain" for update in retention_updates):
        await fabric.close()
        return fail("unexpected_release_recommendation", retention_updates)

    print(
        "PASS milestone4="
        + json.dumps(
            {
                "token": TOKEN,
                "goal_id": goal.get("goal_id"),
                "proposal_manifest_count": len(proposal_manifests),
                "assignment_manifest_count": len(assignment_manifests),
                "retention_update_count": len(retention_updates),
                "assigned_skills": sorted(assigned_skills),
                "retention_recommendations": {
                    update.get("skill_id"): update.get("lifecycle_recommendation")
                    for update in retention_updates
                },
            },
            sort_keys=True,
        )
    )
    await fabric.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
