# RFC-004 — Node Identity & Plasticity

| Field | Value |
|---|---|
| RFC | 004 |
| Title | Node Identity & Plasticity |
| Status | Draft |
| Version | 0.2 |

---

## Problem

Most distributed systems define a node by what it does — its role, its model, its function.

This creates brittle architectures. When the model changes, the node "becomes" something different. When a new capability is needed, a new node type must be defined.

The problem is the assumption: that identity and capability are the same thing.

---

## Motivation

A neuron is not a "vision neuron" in any permanent sense.

What defines a neuron is its structure, its connections, and its capacity to fire. What it *does* — which function it serves — depends on context, on which connections are active, on what the system currently needs.

This is neuroplasticity. And it is why the brain can recover from injury, learn new skills, and reassign resources as needs change.

CAS Fabric applies the same principle:

**Node identity is stable. Node capability is transient.**

What a node is doing today is not what defines it. What defines it is its compute capacity, its memory, its power envelope — and its ability to acquire, run, and release skills.

---

## Specification

### 1. Node Identity

Node identity is permanent for the lifetime of the node. It does not change when skills are acquired or released.

```json
{
  "node_id": "string (UUID)",
  "created_at": "ISO8601",
  "hardware_class": "string",
  "compute_capacity": {
    "cpu_cores": 0,
    "ram_gb": 0.0,
    "has_npu": false,
    "has_gpu": false,
    "power_envelope_watts": 0.0
  },
  "fabric_version": "string"
}
```

`node_id` is assigned once and never changes.  
`hardware_class` is a free-form string describing the physical device (e.g., "android-snapdragon-8g2", "mac-mini-m1", "raspberry-pi-5").

### 2. Skill Manifest

The Skill Manifest is the node's current capability advertisement. It changes as skills are loaded and released.

```json
{
  "node_id": "string",
  "timestamp": "ISO8601",
  "active_skills": [
    {
      "skill_id": "string",
      "version": "string",
      "latency_p50_ms": 0,
      "latency_p95_ms": 0,
      "energy_per_inference_mwh": 0.0,
      "loaded_at": "ISO8601"
    }
  ],
  "available_capacity": {
    "ram_free_gb": 0.0,
    "cpu_load": 0.0,
    "accepting_new_skills": true
  }
}
```

The Skill Manifest is published to the Autonomic Layer at regular intervals, and whenever a skill is loaded or released.

### 3. Skill Lifecycle

A skill passes through four states:

```
AVAILABLE   — exists in Skill Genome, not loaded on this node
LOADING     — being acquired from Skill Genome
ACTIVE      — loaded and available for task assignment
RELEASING   — being unloaded to free capacity
```

Transitions:

```
AVAILABLE → LOADING    triggered by: node decision or Coordinator request
LOADING   → ACTIVE     triggered by: successful skill load
ACTIVE    → RELEASING  triggered by: retention score below threshold, or explicit release
RELEASING → AVAILABLE  triggered by: successful unload
```

### 4. Retention Score

Each active skill maintains a retention score that determines how long it stays loaded.

```
retention_score = 
    w1 * utilization_rate        (how often used in last N days)
  + w2 * recency_score           (time since last use)
  - w3 * memory_footprint        (RAM consumed)
  - w4 * energy_cost             (power draw while loaded)
  + w5 * ecosystem_demand        (how many goals in fabric require this skill)
```

When `retention_score` falls below `release_threshold` (implementation-defined, recommended default: 0.2), the node initiates skill release.

This is **forgetting as adaptation** — not failure.

### 5. Node Health Signal

Extended from RFC-001 to include skill state:

```json
{
  "node_id": "string",
  "timestamp": "ISO8601",
  "status": "healthy | degraded | unavailable",
  "load": 0.0,
  "version": "string",
  "active_skill_count": 0,
  "accepting_goals": true,
  "skill_manifest_hash": "string"
}
```

`skill_manifest_hash` allows the fabric to detect when a node's capabilities have changed without fetching the full manifest.

### 6. Discovery by Capability

Nodes are discovered by skill, not by address.

```
Query:  "Who has speech.transcribe active?"
Answer: [node_id, latency_p50, current_load]

Query:  "Who can load speech.transcribe within 30 seconds?"
Answer: [node_id, estimated_load_time, available_capacity]
```

The second query form enables pre-emptive skill loading for anticipated tasks.

---

## Examples

### Node skill lifecycle (pseudocode)

```python
# Node self-manages skill retention
async def retention_loop(node: Node):
    while True:
        for skill in node.active_skills:
            score = compute_retention_score(skill, node.ecosystem_context)
            if score < RELEASE_THRESHOLD:
                await node.release_skill(skill.skill_id)
                await fabric.publish("node.skill_released", {
                    "node_id": node.id,
                    "skill_id": skill.skill_id,
                    "reason": "retention_score_below_threshold"
                })
        await sleep(RETENTION_CHECK_INTERVAL)
```

### Skill manifest update on load

```python
async def load_skill(node: Node, skill_id: str):
    skill = await genome.fetch(skill_id)
    await node.install(skill)
    node.skill_manifest.active_skills.append(skill.to_manifest_entry())
    await fabric.publish("node.manifest_updated", node.skill_manifest)
```

---

## Hardware Notes

This RFC is hardware-agnostic. However, the following observations are relevant for implementors building physical node clusters:

- Nodes with NPU support (e.g., Snapdragon 8-series) will have significantly better energy efficiency for inference workloads
- Skill `energy_per_inference_mwh` should be measured on actual hardware, not estimated
- Thermal throttling affects `latency_p95` more than `latency_p50` — both should be tracked
- USB-C power delivery stability matters for always-on node deployments

These are implementation considerations, not protocol requirements.

---

## Open Questions

- Should `skill_id` be a namespace like `domain.function.version` (e.g., `speech.transcribe.v2`) or a UUID?
- Who governs the Skill Genome? Is it a community repository, a private registry, or both?
- Should nodes be able to share loaded skills peer-to-peer, or must all skill acquisition go through the Genome?
- How should the protocol handle a skill that becomes unavailable in the Genome while nodes are running it?

---

## CAS Test

| Question | Answer |
|---|---|
| Is it local? | Yes — retention decisions are made by each node independently |
| Is it composable? | Yes — any node can join the fabric and advertise its manifest |
| Is it adaptive? | Yes — skill composition changes dynamically without protocol change |
| Is it emergent? | Yes — ecosystem capability profile emerges from individual node decisions |
| Is it implementation-independent? | Yes — hardware, OS, and model choices are entirely up to the implementor |
