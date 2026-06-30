# Principles

> *The heart of this project is not the RFCs. It is this document.*

Every RFC, every schema, every design decision in CAS Fabric Protocol must be traceable back to the principles written here.

When in doubt, return here.

---

## Foundation

A Complex Adaptive System is defined by its **interactions**, not its components.

Intelligence in such a system does not reside in any single node. It emerges from the quality of cooperation between nodes.

This has one profound implication:

**The protocol matters more than any individual implementation.**

A great protocol with mediocre implementations will produce a functioning ecosystem.  
A mediocre protocol with great implementations will produce isolated brilliance that cannot cooperate.

---

## The Seven Design Principles

### Principle 1 — Favor Adaptation Over Optimization

An adaptive system survives technological change.  
An optimized system survives only today's assumptions.

Design for change. Not for today's hardware, today's models, or today's constraints.

### Principle 2 — Favor Decentralized Coordination Over Centralized Control

Whenever possible, behavior should **emerge** from interactions between participants.

A permanent central orchestrator is a single point of failure — architecturally and philosophically.

Coordination should arise naturally from nodes that understand their own context, share a common memory fabric, and follow agreed contracts.

### Principle 3 — Define Contracts, Never Implementations

The protocol specifies **what must be observable**.

It never specifies how participants achieve that behavior internally.

Implementors are free to choose any language, model, database, or infrastructure — as long as the observable contract is satisfied.

### Principle 4 — Reuse Existing Terminology Whenever Possible

New vocabulary should only be introduced when existing terms cannot accurately express a CAS concept.

Cognitive overhead is a real cost. Every new term must earn its place.

### Principle 5 — Interoperability Is the Primary Objective

Every compliant implementation must be able to cooperate with every other compliant implementation — regardless of language, framework, hardware, or AI model.

A specification that only works with one implementation is not a specification. It is documentation.

### Principle 6 — Evolve Without Breaking Ecosystems

The protocol should evolve. But existing compliant implementations should not break when it does.

Backward compatibility is a design objective, not an afterthought.

### Principle 7 — Forgetting Is Adaptation, Not Failure

In biological systems, forgetting is how the brain makes room to learn.

In CAS Fabric, skill release is a first-class mechanism — not cache cleanup.

A node that releases an unused skill is not losing capability. It is maintaining adaptability.

The ecosystem's collective memory persists in the Skill Genome. Individual nodes remain lean.

---

## The CAS Test

Before any feature is accepted into this protocol, it must pass five questions.

This is not a checklist. It is a compass.

```
┌─────────────────────────────────────────────────────────┐
│                    THE CAS TEST                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  1. IS IT LOCAL?                                        │
│     Can the decision be made with local knowledge?      │
│     A feature that requires global state to function    │
│     is a coordination bottleneck in disguise.           │
│                                                         │
│  2. IS IT COMPOSABLE?                                   │
│     Can it combine with other nodes without             │
│     requiring modification on either side?              │
│                                                         │
│  3. IS IT ADAPTIVE?                                     │
│     Can behavior change without changing the protocol?  │
│     The protocol should be stable. Behavior flexible.   │
│                                                         │
│  4. IS IT EMERGENT?                                     │
│     Does coordination arise from interaction —          │
│     or is it imposed by a central controller?           │
│                                                         │
│  5. IS IT IMPLEMENTATION-INDEPENDENT?                   │
│     Are implementors free to choose their language,     │
│     model, database, and infrastructure?                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

If any answer is **no**, the feature must be redesigned before entering the specification.

---

## The Nervous System Model

The architecture of CAS Fabric Protocol is inspired by the biological nervous system — the most battle-tested adaptive system known.

It has been running for 500 million years.

```
AUTONOMIC LAYER
  Infrastructure that runs without conscious overhead.
  Heartbeat, health, routing, logging, synchronization.
  Always on. Never interrupted. Zero reasoning required.

LIMBIC LAYER  
  Active memory fabric. Values. Fast-path decisions.
  Pattern matching, relevance scoring, threat detection.
  Always present as context — not called, but felt.

NEOCORTEX LAYER
  Reasoning. Planning. Language. Creativity.
  Slow, expensive, powerful.
  Called only when the layers below cannot resolve.
```

The LLM lives in the neocortex layer.

It is not the operating system.

---

## The Plasticity Model

A node is not defined by the skill it runs today.

A node is a compute unit with three properties:

```
IDENTITY    — stable, persistent, unique
CAPACITY    — compute, memory, power envelope
PLASTICITY  — ability to acquire, run, and release skills
```

Skills are transient expressions of capacity, not permanent identities.

The ecosystem's complete skill space lives in the Skill Genome — a shared repository from which any node may acquire what it needs and return what it no longer uses.

---

## The Values Fabric

One principle stands apart from all others.

**Values must be a fabric, not a filter.**

A values filter sits at the end of a pipeline and vetoes bad outputs.  
A values fabric permeates every layer and makes bad outputs less natural to produce.

The difference is not philosophical. It is architectural.

A filter can be bypassed.  
Gravity cannot.

Any compliant implementation of CAS Fabric Protocol must implement values as a component of the Memory Fabric — not as an agent, not as a post-processing step, not as a system prompt.

Values are the field within which all nodes operate.

---

## What This Protocol Is Not Trying to Solve

- It does not define how to train better models.
- It does not define how to make individual nodes smarter.
- It does not solve the alignment problem.
- It does not replace human judgment.

It solves one problem:

**How do many autonomous intelligent systems cooperate without losing their autonomy?**

Everything else is out of scope.
