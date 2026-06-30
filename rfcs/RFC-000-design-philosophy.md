# RFC-000 — Design Philosophy

| Field | Value |
|---|---|
| RFC | 000 |
| Title | Design Philosophy & Constitution |
| Status | Draft |
| Version | 0.1 |
| Created | 2025 |

---

## Problem

Every technical decision in a long-lived specification eventually faces the same question:

*Why was this designed this way?*

Without a written answer, every RFC becomes an island. Contributors guess at intent. Inconsistencies accumulate. The specification loses coherence over time.

RFC-000 exists so that every future RFC has a foundation to refer back to.

---

## Motivation

CAS Fabric Protocol emerged from a practical problem:

Building a personal AI operating system revealed that the dominant paradigm — one large model as the center of everything — is architecturally limiting.

Not because the models are not capable enough.  
But because **organization matters more than capability**.

The human neocortex is only 2mm thick. Its power comes not from raw size but from how it is organized — and crucially, from the layers beneath it that handle 95% of processing before anything reaches conscious reasoning.

This observation is the genesis of this protocol.

---

## Scope

### This protocol specifies:

- Common vocabulary for describing cooperative intelligent systems
- Interaction contracts between autonomous nodes
- Interoperability rules across implementations
- Behavioral constraints that ensure emergent coordination

### This protocol intentionally does not specify:

- Programming languages
- Machine learning models
- Databases or storage systems
- Operating systems
- Communication transports
- Deployment architectures
- Training procedures

These choices belong entirely to implementors.

---

## Design Goal

The objective is not to build a better AI.

The objective is to provide a protocol that allows many independent intelligent systems to cooperate while remaining autonomous.

The protocol should remain useful even if every AI technology available today becomes obsolete.

---

## First Principles

Every design decision within this protocol derives from six principles.

**Principle 1 — Favor adaptation over optimization.**

An adaptive system survives technological change. An optimized system survives only today's assumptions. Never optimize for today's hardware.

**Principle 2 — Favor decentralized coordination over centralized control.**

Behavior should emerge from interactions between participants rather than from a permanent coordinator. A permanent central orchestrator is a single point of failure — architecturally and philosophically.

**Principle 3 — Define contracts, never implementations.**

The protocol specifies what must be observable. It never specifies how participants achieve that behavior internally.

**Principle 4 — Reuse existing software engineering terminology whenever possible.**

New terminology should only be introduced when existing terms cannot accurately express a CAS concept. The protocol aims to reduce cognitive overhead for implementors.

**Principle 5 — Interoperability is the primary objective.**

Every compliant implementation should be able to cooperate with every other compliant implementation regardless of language, framework, hardware, or AI model.

**Principle 6 — The protocol should evolve without breaking existing ecosystems whenever reasonably possible.**

Backward compatibility is a design objective.

---

## Architectural Model

CAS Fabric Protocol organizes cooperative intelligence in three layers, derived from the architecture of the biological nervous system.

```
┌────────────────────────────────────────┐
│           NEOCORTEX LAYER              │
│   Reasoning nodes — LLM, planners,     │
│   language, creativity                 │
│   Called only when necessary           │
├────────────────────────────────────────┤
│            LIMBIC LAYER                │
│   Active Memory Fabric — values,       │
│   relevance, fast-path decisions,      │
│   emotional signals, context           │
│   Always present, never called         │
├────────────────────────────────────────┤
│          AUTONOMIC LAYER               │
│   Infrastructure — health, routing,    │
│   logging, synchronization             │
│   Always running, zero overhead        │
└────────────────────────────────────────┘
```

This is not a strict hierarchy. It is a model of cognitive cost.

The autonomic layer runs without reasoning.  
The limbic layer runs with pattern matching, not deliberation.  
The neocortex layer runs with full reasoning — and pays the full computational cost.

A well-designed system minimizes neocortex invocations.

---

## The Values Fabric Requirement

This is the most important architectural constraint in this specification.

**Values must be implemented as a fabric, not as an agent or filter.**

### What this means

A values agent receives an output and decides whether to approve or veto it.  
A values fabric permeates the memory layer and shapes what every node considers as context.

The difference:

```
Values as filter (wrong):
  Node produces output → Values agent checks → Approve or veto

Values as fabric (correct):
  Values embedded in Memory Fabric
  → Every node receives value-weighted context
  → Bad outputs become less natural to produce
  → Values are gravity, not a gate
```

### Why this matters

A filter can be bypassed — by design changes, by edge cases, by prompt engineering.  
Gravity cannot be bypassed. It is the medium through which everything moves.

Any implementation claiming compliance with CAS Fabric Protocol must implement values as a component of the Memory Fabric layer — not as a post-processing step, not as a system prompt prepended to each call.

---

## Non-Goals

CAS Fabric Protocol is not:

- An AI framework
- An orchestration engine
- A service mesh
- An agent implementation
- An operating system
- A reference architecture
- A solution to the alignment problem

It is a protocol.

---

## Design Review Questions

Before introducing any new feature into the protocol, contributors must ask:

1. Does this improve interoperability between independent implementations?
2. Does this reduce unnecessary assumptions about technology choices?
3. Can independent implementations adopt this without coordination with each other?
4. Does this preserve implementation freedom?
5. Is this principle derived from Complex Adaptive Systems theory rather than from a specific technology?

Features that fail these questions must be reconsidered.

---

## The CAS Test

Every RFC must pass before acceptance:

1. **Is it local?** Can the decision be made with local knowledge only?
2. **Is it composable?** Can it combine with other nodes without modification?
3. **Is it adaptive?** Can behavior change without changing the protocol?
4. **Is it emergent?** Does coordination arise from interaction, not central control?
5. **Is it implementation-independent?** Are implementors free to choose their stack?

---

## Open Questions

- How should the protocol handle versioning when nodes run different RFC versions simultaneously?
- What is the minimal viable contract for a node to be considered compliant?
- How should the Values Fabric handle conflicts between values of equal weight?

---

## References

- Complex Adaptive Systems — Holland, J.H. (1992)
- Global Workspace Theory — Baars, B.J. (1988)
- Thinking, Fast and Slow — Kahneman, D. (2011)
- The CAS Test — PRINCIPLES.md, this repository
