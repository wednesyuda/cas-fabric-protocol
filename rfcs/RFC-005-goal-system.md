# RFC-005 — Goal System

| Field | Value |
|---|---|
| RFC | 005 |
| Title | Goal System |
| Status | Draft |
| Version | 0.2 |

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

### 2. Goal Lifecycle

```
created -> broadcast -> assigned -> executing -> completed
                                      \-> failed
created -> suspended
```

### 3. Goal Capabilities

The reference capability surface is:

```
goal.create
goal.status
goal.update
goal.submit
goal.complete
```

`goal.submit` may create an implicit goal, or process an existing `goal_id`.

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
