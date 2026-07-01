"""
Skill Genome reference helpers (RFC-006 + RFC-004).

The Genome is passive capability memory. This module keeps the reference
runtime small by providing local skill definitions that workers can advertise
through Task Auction proposals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


GENOME_PROTOCOL_VERSION = "cas-fabric.skill-genome.v0.1"


@dataclass(frozen=True)
class SkillGenomeEntry:
    skill_id: str
    capability: str
    version: str
    description: str
    input_contract: dict[str, Any]
    output_contract: dict[str, Any]
    constraints: dict[str, Any]
    metrics: dict[str, Any]
    retention_hints: dict[str, Any]

    def to_manifest(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["type"] = "skill.manifest"
        payload["protocol"] = GENOME_PROTOCOL_VERSION
        return payload


DEFAULT_SKILL_GENOME: dict[str, SkillGenomeEntry] = {
    "memory.query": SkillGenomeEntry(
        skill_id="memory.query",
        capability="memory.query",
        version="v0.1",
        description="Retrieve relevant memory records for an intent.",
        input_contract={"query": "string", "limit": "integer"},
        output_contract={"ok": "boolean", "results": "array"},
        constraints={"requires_values_context": True, "side_effects": "read-only"},
        metrics={"typical_latency_ms": 100, "typical_energy_mwh": 0.1},
        retention_hints={"default_retention_score": 0.65, "release_threshold": 0.2},
    ),
    "reasoning.llm": SkillGenomeEntry(
        skill_id="reasoning.llm",
        capability="reasoning.llm",
        version="v0.1",
        description="Produce a concise answer from a prepared reasoning envelope.",
        input_contract={"intent": "string", "reasoning_request": "object"},
        output_contract={"ok": "boolean", "output": "string"},
        constraints={"requires_prepared_context": True, "requires_values_signature": True},
        metrics={"typical_latency_ms": 1000, "typical_energy_mwh": 1.0},
        retention_hints={"default_retention_score": 0.70, "release_threshold": 0.2},
    ),
}


def manifest_for_skill(skill_id: str) -> dict[str, Any]:
    entry = DEFAULT_SKILL_GENOME.get(skill_id)
    if entry:
        return entry.to_manifest()
    return SkillGenomeEntry(
        skill_id=skill_id,
        capability=skill_id,
        version="v0.1",
        description="Implementation-defined capability.",
        input_contract={},
        output_contract={},
        constraints={},
        metrics={"typical_latency_ms": 999999, "typical_energy_mwh": 1.0},
        retention_hints={"default_retention_score": 0.5, "release_threshold": 0.2},
    ).to_manifest()


def manifests_for_skills(skill_ids: list[str]) -> list[dict[str, Any]]:
    return [manifest_for_skill(skill_id) for skill_id in skill_ids]


def retention_update(manifest: dict[str, Any], success: bool) -> dict[str, Any]:
    hints = manifest.get("retention_hints", {})
    previous = float(hints.get("default_retention_score", 0.5))
    delta = 0.1 if success else -0.2
    score = min(1.0, max(0.0, previous + delta))
    release_threshold = float(hints.get("release_threshold", 0.2))
    return {
        "type": "skill.retention_update",
        "protocol": GENOME_PROTOCOL_VERSION,
        "skill_id": manifest.get("skill_id"),
        "previous_retention_score": previous,
        "retention_delta": delta,
        "retention_score": score,
        "release_threshold": release_threshold,
        "lifecycle_recommendation": "retain" if score >= release_threshold else "release",
    }
