# RFC-006 — Skill Genome

| Field | Value |
|---|---|
| RFC | 006 |
| Title | Skill Genome |
| Status | Draft |
| Version | 0.1 |

---

## Problem

If skills are transient expressions of node capacity (RFC-004), then there must be a persistent, shared repository from which nodes can acquire skills and to which they return them when done.

Without this, skills disappear when nodes release them. The ecosystem loses capability it has already built.

---

## Motivation

In biology, skills are not stored in neurons. They are stored in DNA.

DNA does not run anything. It does not execute. It is not the muscle.

DNA is the blueprint from which any cell can express a capability when the organism needs it.

The Skill Genome plays the same role in CAS Fabric.

It is not an orchestrator.  
It is not a model registry in the traditional sense.  
It is the **collective memory of capability** — the pool from which the living ecosystem expresses itself.

A node that releases a skill does not destroy it. The skill returns to the Genome, available for any other node to acquire.

This is how the ecosystem learns without any single node needing to remember everything.

---

## Specification

### 1. Definition

The Skill Genome is a shared, persistent repository of skills available to all nodes in the CAS Fabric ecosystem.

It is passive storage. It does not route, orchestrate, or decide. It stores and serves.

Intelligence about *which* skills to acquire lives in nodes and the Memory Fabric. The Genome simply makes skills available.

### 2. Skill Definition

A Skill is a self-contained unit of capability that a node can load, execute, and release.

```json
{
  "skill_id": "string",
  "domain": "string",
  "function": "string",
  "version": "string",
  "description": "string",
  "input_schema": {},
  "output_schema": {},
  "requirements": {
    "min_ram_gb": 0.0,
    "requires_npu": false,
    "requires_gpu": false,
    "min_storage_gb": 0.0
  },
  "metrics": {
    "typical_latency_ms": 0,
    "typical_energy_mwh": 0.0,
    "model_size_gb": 0.0
  },
  "tags": ["string"],
  "license": "string",
  "source_url": "string"
}
```

### 3. Skill Namespacing

Skill IDs follow a three-part dot-notation:

```
domain.function.version

Examples:
  speech.transcribe.v1
  vision.ocr.v2
  text.summarize.v1
  text.embed.v3
  audio.detect_language.v1
  document.extract_tables.v1
  code.review.v1
  reasoning.plan.v2
```

This enables discovery by domain, by function, or by exact version.

### 4. Genome API

The Skill Genome exposes four operations:

```
GET  /skills                    — list all available skills
GET  /skills/{skill_id}         — get skill definition
GET  /skills?domain={domain}    — list skills by domain
GET  /skills?tags={tag}         — list skills by tag

POST /skills/{skill_id}/acquire — node requests skill package
POST /skills                    — publish a new skill (governed)
```

Acquire returns the installable skill package — model weights, runtime configuration, input/output adapter.

### 5. Skill Categories

The Genome organizes skills into categories. This list is not exhaustive — it is a starting taxonomy.

```
speech.*        — transcription, synthesis, language detection
vision.*        — OCR, image captioning, object detection
text.*          — summarization, embedding, translation, classification
audio.*         — analysis, fingerprinting
document.*      — parsing, extraction, formatting
reasoning.*     — planning, evaluation, judgment
code.*          — generation, review, execution
memory.*        — retrieval, indexing, clustering
tool.*          — API calls, web search, file operations
sensor.*        — data ingestion from physical sensors
```

### 6. Relationship to External API Registries

The Genome may index skills that wrap external APIs — similar to repositories like API Mega List.

In this model, a "skill" is not only a locally-run model. A skill may be:

- A locally-run model (e.g., Whisper for speech.transcribe)
- A wrapper around an external API (e.g., weather.current via OpenWeatherMap)
- A hybrid (local first, API fallback)

The node does not need to know which kind it is loading. The skill's interface contract is identical regardless of implementation.

This is the protocol's Principle 3 applied to skills: define contracts, never implementations.

### 7. Ecosystem Demand Signal

The Skill Genome maintains an aggregate demand signal — how frequently each skill is being acquired across the ecosystem.

```json
{
  "skill_id": "string",
  "acquisition_count_30d": 0,
  "active_node_count": 0,
  "ecosystem_demand_score": 0.0
}
```

This signal feeds into RFC-004's retention score calculation — nodes can factor ecosystem demand when deciding whether to retain or release a skill.

A skill in high ecosystem demand should be retained by more nodes, making it faster to acquire and reducing coordination latency.

---

## Examples

### Node acquiring a skill before auction

```python
# Anticipatory loading based on ecosystem demand signal
async def preload_high_demand_skills(node: Node, genome: Genome):
    high_demand = await genome.list_skills(
        sort_by="ecosystem_demand_score",
        limit=5
    )
    for skill in high_demand:
        if node.can_load(skill) and skill.skill_id not in node.active_skills:
            await node.load_skill(skill.skill_id)
```

### Skill release returning to genome availability

```python
# When a node releases a skill, it notifies the fabric
# The genome does not need to do anything — the skill was never "removed"
# Other nodes can always acquire it
async def release_skill(node: Node, skill_id: str):
    await node.uninstall(skill_id)
    await fabric.publish("node.skill_released", {
        "node_id": node.id,
        "skill_id": skill_id
    })
    # Genome remains unchanged — skill still available for any node
```

---

## Open Questions

- Who governs skill publication? Open submission, curated registry, or both?
- How should skill versioning handle breaking changes in input/output schemas?
- Should the Genome support peer-to-peer skill transfer between nodes, bypassing central acquisition?
- How should the Genome handle skills that require proprietary API keys?
- What is the minimum viable Genome — a git repository? A simple HTTP server? A distributed DHT?

---

## CAS Test

| Question | Answer |
|---|---|
| Is it local? | Yes — each node decides independently what to acquire |
| Is it composable? | Yes — any skill can be loaded by any compatible node |
| Is it adaptive? | Yes — ecosystem capability profile shifts as demand changes |
| Is it emergent? | Yes — collective capability emerges from individual node decisions |
| Is it implementation-independent? | Yes — the Genome can be a git repo, an HTTP registry, or a DHT |
