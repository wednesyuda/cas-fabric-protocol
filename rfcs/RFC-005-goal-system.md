# RFC-005 — Goal System

| Field | Value |
|---|---|
| RFC | 005 |
| Title | Goal System |
| Status | Draft |
| Version | 0.3 |

---

## Problem

Modern AI systems wait. They respond to prompts and then go idle.

A cooperative intelligent system should be capable of maintaining persistent objectives that exist independently of prompts — monitoring, following up, improving itself.

---

## Specification

### 1. Goal Object

```json
{
  "goal_id": "string",
  "intent": "string",
  "required_skills": ["string"],
  "priority": "low | medium | high",
  "state": "created | broadcast | assigned | executing | completed | failed | suspended",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "history": []
}
```

### 2. Goal Store

Goals are persistent Fabric-addressable objects.

The protocol does not require a specific storage backend. A reference
implementation may use a local JSON file, embedded database, or in-memory store
for canaries. Production deployments SHOULD route durable goal state through the
Memory Fabric or a backing store with equivalent auditability, lifecycle
integrity, and recovery behavior.

The store must preserve:

- current goal state
- creation and update timestamps
- required skills
- priority
- lifecycle history
- assignment and result metadata where available

### 3. Goal Lifecycle

```
created -> broadcast -> assigned -> executing -> completed
                                      \-> failed
created -> suspended
```

Every lifecycle transition SHOULD append a history event:

```json
{
  "state": "assigned",
  "timestamp": "ISO8601",
  "metadata": {}
}
```

Implementations MUST reject transitions for unknown goal IDs.

### 4. Goal Capabilities

The reference capability surface is:

```
goal.create
goal.status
goal.update
goal.submit
goal.complete
```

`goal.submit` may create an implicit goal, or process an existing `goal_id`.

#### 4.1 `goal.create`

Creates a persistent goal object in `created` state.

Required fields:

- `intent`
- `required_skills`

Optional fields:

- `priority`

#### 4.2 `goal.status`

Returns the current goal object and lifecycle history for a known `goal_id`.

#### 4.3 `goal.update`

Updates mutable fields such as intent, priority, required skills, or state. The
update must be recorded in lifecycle history.

#### 4.4 `goal.submit`

Submits a goal into the Task Auction flow defined in RFC-003 Interface B.

If a `goal_id` is supplied, the existing goal is used. If no `goal_id` is
supplied, the implementation may create an implicit goal before broadcasting.

The canonical lifecycle for a successful submitted goal is:

```
created -> broadcast -> assigned -> executing -> completed
```

If no valid assignment exists, required skills remain unassigned, or execution
fails, the final state is `failed`.

#### 4.5 `goal.complete`

Marks a goal as completed with result metadata. This is useful for externally
executed goals where execution is not owned by the local Task Auction loop.

### 5. Relationship to Task Auction

The Goal System defines persistent intent. RFC-003 Interface B defines how work
is auctioned.

The boundary is:

- Goal System owns goal identity, lifecycle, and history.
- Task Auction owns proposal collection, assignment selection, and execution
  result reporting.
- Reflection/Adaptive Scoring may update future assignment ranking based on
  execution outcomes, but it does not rewrite goal history.

### 6. Reflection State

Reflection state is adjacent to, but distinct from, goal state.

An implementation may record execution outcomes per skill so future auctions can
favor skills or nodes with stronger recent performance. This adaptive confidence
MUST be treated as ranking input, not as a guarantee of correctness.

Reference implementations may store reflection state locally. Production
deployments SHOULD persist it through the Memory Fabric or an equivalent
auditable substrate.

### 7. Failure Semantics

A goal failure is a lifecycle result, not a protocol crash.

Implementations SHOULD distinguish at least:

- no valid proposals
- partial assignment
- executor mapping missing
- execution timeout
- skill returned non-ok response

The failed goal should remain queryable through `goal.status`.

---

## Key Insight

Goals should live in the Limbic Layer (Memory Fabric), not in the Neocortex Layer.

A goal is not a reasoning task. It is a persistent context that shapes what the system considers relevant — much like hunger shapes what a biological organism pays attention to.

---

## CAS Test

| Question | Answer |
|---|---|
| Is it local? | Yes — each node can inspect and act on goal state through Fabric capabilities |
| Is it composable? | Yes — goals are ordinary Fabric-addressable objects |
| Is it adaptive? | Yes — lifecycle state can change without changing the protocol |
| Is it emergent? | Yes — execution emerges through Task Auction rather than central scripting |
| Is it implementation-independent? | Yes — persistence can be memory, file, database, or another substrate |

---

## Open Questions

- Who can create goals? Any node, or only designated nodes?
- Can goals conflict? How is conflict resolved?
- Should goals have expiry?
- How does the system avoid goal proliferation?

---
