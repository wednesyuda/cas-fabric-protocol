# RFC-002 — Memory Fabric

| Field | Value |
|---|---|
| RFC | 002 |
| Title | Memory Fabric |
| Status | Draft |
| Version | 0.1 |

---

## Problem

Today's AI memory systems are passive.

They wait to be queried.  
They return data without context.  
They have no awareness of what is currently happening in the system.  
They cannot interrupt when they know something relevant.

This is a filing cabinet, not a cognitive component.

---

## Motivation

The biological hippocampus does not wait to be asked. It participates.

When you are planning tomorrow's schedule, your memory surfaces the meeting you forgot — without being prompted. The memory system observed your current context, assessed relevance, and interrupted with useful information.

This is the model for the CAS Fabric Memory layer.

Memory is not storage. Memory is an **active cognitive participant**.

---

## Specification

### 1. Definition

The Memory Fabric is the shared cognitive substrate of the CAS ecosystem. It is the implementation of the Limbic Layer defined in RFC-000.

It has two distinct responsibilities:

1. **Passive Store** — respond to explicit queries from nodes
2. **Active Broadcast** — proactively surface relevant information to nodes based on observed context

### 2. Memory Types

The Memory Fabric must support four memory types, analogous to human memory systems:

**2.1 Working Memory**  
Current task context. Short-lived. High-priority retrieval.  
Analogous to: prefrontal cortex working memory buffer.

**2.2 Episodic Memory**  
What happened, when, and in what sequence.  
Analogous to: hippocampal episodic encoding.

**2.3 Semantic Memory**  
Facts, knowledge, relationships. Persistent.  
Analogous to: cortical long-term semantic storage.

**2.4 Values Memory**  
The ethical and philosophical fabric of the system. See Section 5.  
Analogous to: limbic emotional valence — always present, never absent.

### 3. Passive Store Interface

Any node may query the Memory Fabric:

```json
{
  "type": "memory.query",
  "node_id": "string",
  "query": "string",
  "memory_types": ["working", "episodic", "semantic"],
  "limit": 10
}
```

The Memory Fabric returns ranked results with relevance scores.

### 4. Active Broadcast — The Two-Channel Model

The Memory Fabric maintains two broadcast channels:

**Channel 1 — Passive Store**  
Standard query/response. Node asks, Memory answers.

**Channel 2 — Active Broadcast**  
Memory observes all messages passing through the fabric.  
When it detects high-relevance information for an active context, it publishes to `memory.broadcast`.

Nodes subscribe to `memory.broadcast` and filter by their declared context.

```
Memory Fabric observes: Planner is working on "schedule for tomorrow"
Memory detects: episodic memory contains "meeting at 09:00 tomorrow"
Memory broadcasts: {
  relevance: 0.94,
  context_match: "schedule planning",
  content: "meeting at 09:00 tomorrow with [...]",
  interrupt_priority: "medium"
}
Planner receives broadcast → incorporates into planning context
```

### 4.1 Relevance Scoring — Fast Path

Relevance scoring must use the Fast Path by default.

Fast Path components (no LLM required):

```
semantic_similarity   — vector distance between query and stored content
recency_score         — exponential decay from last access time  
source_authority      — weight assigned to the writing node
urgency_flag          — time-sensitive marker set at write time
context_overlap       — keyword and entity matching against active context
```

Final relevance score:

```
R = w1 * semantic_similarity
  + w2 * recency_score
  + w3 * source_authority
  + w4 * urgency_flag
  + w5 * context_overlap
```

Weights are implementation-defined. The formula structure is protocol-defined.

### 4.2 Relevance Scoring — Slow Path

When Fast Path confidence falls below threshold, the Memory Fabric may invoke a Reasoning Node for semantic judgment.

This must be rare. The slow path is the exception, not the default.

Threshold for slow path invocation is implementation-defined with a recommended default of confidence < 0.4.

### 5. Values Memory — The Ethical Gravity Requirement

This section implements the Values Fabric Requirement from RFC-000.

**Values Memory is not a separate agent. It is a component of the Memory Fabric itself.**

#### 5.1 Structure

Values Memory stores the system's ethical and philosophical principles as weighted embeddings.

```json
{
  "value_id": "string",
  "principle": "string",
  "weight": 0.0,
  "domain": ["action", "communication", "decision", "relationship"],
  "embedding": [...]
}
```

#### 5.1.1 Runtime Configuration

Values Memory MUST be configurable at runtime in production deployments.

A reference implementation may ship with a small set of seed values so the
system can boot, run canaries, and demonstrate the Values Gravity contract
without requiring an external governance service. These seed values are
defaults, not protocol law.

Production implementations SHOULD allow governed write/update flows for Values
Memory through the same Memory Fabric boundary used for other memory types. The
protocol intentionally does not define a global authority for value updates; it
only requires that values consulted during context preparation are explicit,
auditable, and represented in the `values_signature`.

#### 5.2 Ethical Gravity Function

Every result returned by the Memory Fabric — whether from passive query or active broadcast — passes through the Ethical Gravity Function before delivery.

```
ethical_score = cosine_similarity(result_embedding, values_embeddings)
adjusted_result = result * (1 + ethical_weight * ethical_score)
```

Results that align with values are surfaced more prominently.  
Results that conflict with values are surfaced with a tension marker.

#### 5.3 Tension Signal

When a node's declared intent conflicts with the Values Memory above a threshold, the Memory Fabric emits a Tension Signal to the requesting node.

```json
{
  "type": "memory.tension",
  "node_id": "string",
  "intent_summary": "string",
  "conflicting_value": "string",
  "tension_score": 0.0,
  "suggested_reframe": "string | null"
}
```

The node receiving a Tension Signal may proceed, adapt, or escalate. The protocol does not prescribe which — only that the signal must be emitted and must not be silently dropped.

#### 5.4 Presence Marker

Every context payload delivered by the Memory Fabric carries a Presence Marker:

```json
{
  "values_signature": {
    "values_consulted": true,
    "tension_detected": false,
    "ethical_alignment_score": 0.87
  }
}
```

This is how Values are always present without being explicitly invoked.

---

## Examples

### Writing to memory

```python
await fabric.memory.write({
    "type": "episodic",
    "content": "Completed invoice reconciliation for March",
    "timestamp": now(),
    "source": "karjuna.executor",
    "urgency": False
})
```

### Querying memory with values context

```python
result = await fabric.memory.query({
    "query": "How should I respond to this supplier complaint?",
    "memory_types": ["episodic", "semantic"],
    "include_values_context": True
})
# result.values_signature.tension_detected → False
# result.content → ranked relevant memories + value-weighted framing
```

---

## Open Questions

- Should Working Memory have a maximum capacity with automatic eviction, or is that implementation-defined?
- How should the Memory Fabric handle conflicting memories — two episodic records that contradict each other?
- Should the Tension Signal block node execution or remain advisory only?
- Who governs writes to Values Memory in multi-operator deployments?
- What audit trail is sufficient for Values Memory updates?

---

## CAS Test

| Question | Answer |
|---|---|
| Is it local? | Yes — relevance scoring uses local context and local embeddings |
| Is it composable? | Yes — any node can read/write without modifying the fabric |
| Is it adaptive? | Yes — relevance weights can evolve without protocol change |
| Is it emergent? | Yes — system awareness emerges from memory observation, not orchestration |
| Is it implementation-independent? | Yes — only interfaces and schemas are specified |
