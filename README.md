# CAS Fabric Protocol

> *Do not build a faster brain. Build a better nervous system.*

An open protocol specification for building distributed adaptive systems where intelligence emerges from cooperation — not from a single central model.

---

## What Does CAS Mean?

**CAS** stands for **Complex Adaptive System** — a term from systems theory describing networks of independent agents (cells, organisms, market participants, neurons) whose interactions produce intelligent, adaptive behavior at the system level, without any single agent controlling the whole.

### Why This Name, and Why Now

The dominant paradigm in AI today treats a single model as the entire system. Make the model bigger, give it a longer context window, add more tools — the model remains the center of everything.

This works, but it has a structural ceiling. A single model is not a Complex Adaptive System. It is one large component, however capable. It does not adapt by reorganizing its parts, because it has no parts to reorganize — only weights to fine-tune at enormous cost.

A Complex Adaptive System, by contrast, gets stronger by changing how its independent parts cooperate — not by making any single part larger. This is how immune systems, markets, ant colonies, and brains all achieve robustness and adaptability that no single component could achieve alone.

CAS Fabric Protocol applies this lens deliberately to the current moment in AI: instead of one model trying to do everything, many smaller, specialized, replaceable nodes cooperate through a shared protocol. The intelligence lives in the cooperation, not in any single node — including the largest one.

The name is the thesis. The protocol exists to make that thesis implementable.

---

## What This Is

CAS Fabric Protocol is an **open specification**, not a library or framework.

It defines how autonomous intelligent nodes communicate, share memory, coordinate decisions, and evolve together — while remaining completely implementation-independent.

Think of it as TCP/IP for cooperative intelligence.

---

## What This Is Not

- Not an AI framework
- Not an agent SDK
- Not an orchestration engine
- Not a service mesh
- Not tied to any language, model, or platform

Reference implementations can live in separate repositories. This repository
also contains a minimal Python reference runtime used to verify that the draft
contracts are coherent.

---

## The Core Insight

Modern AI systems are becoming increasingly capable, yet they remain isolated.

Each framework defines its own agent model.  
Each platform invents its own communication format.  
Each implementation develops its own memory system.

CAS Fabric Protocol provides a **shared language** that enables autonomous systems to cooperate while remaining free to evolve independently.

The architecture is inspired by the biological nervous system:

```
AUTONOMIC LAYER    — infrastructure that runs without conscious overhead
LIMBIC LAYER       — active memory fabric, values, fast-path decisions  
NEOCORTEX LAYER    — reasoning nodes, called only when truly needed
```

The LLM is one node. Not the operating system.

---

## The Five Principles

Before any feature enters this protocol, it must pass **The CAS Test**:

| Question | Principle |
|---|---|
| Is it local? | Can decisions be made with local knowledge only? |
| Is it composable? | Can it combine with other nodes without modification? |
| Is it adaptive? | Can behavior change without changing the protocol? |
| Is it emergent? | Does coordination arise from interaction, not central control? |
| Is it implementation-independent? | Are implementors free to choose language, model, and infrastructure? |

If all five answers are yes, the feature belongs here.

---

## Repository Structure

```
cas-fabric-protocol/
│
├── README.md               ← you are here
├── PRINCIPLES.md           ← the heart of this project
├── CONTRIBUTING.md
├── LICENSE
│
├── docs/
│   ├── philosophy.md       ← why this exists
│   ├── terminology.md      ← shared vocabulary
│   └── roadmap.md          ← where we are going
│
├── rfcs/
│   ├── RFC-000-design-philosophy.md
│   ├── RFC-001-autonomic-layer.md
│   ├── RFC-002-memory-fabric.md
│   ├── RFC-003-reasoning-interface.md
│   ├── RFC-004-node-identity.md
│   ├── RFC-005-goal-system.md
│   └── RFC-006-skill-genome.md
│
├── schemas/
│   ├── node.schema.json
│   ├── message.schema.json
│   ├── capability.schema.json
│   ├── memory.schema.json
│   └── goal.schema.json
│
├── reference/
│   └── python/              ← minimal runtime canaries and services
│
├── deploy/
│   └── systemd/user/        ← generic user-service templates
│
├── reports/                 ← generalized runtime verification reports
│
└── examples/
    ├── python/
    ├── typescript/
    └── go/
```

---

## Current RFC Status

| RFC | Title | Status |
|---|---|---|
| RFC-000 | Design Philosophy & Constitution | Draft |
| RFC-001 | Autonomic Layer | Draft |
| RFC-002 | Memory Fabric | Draft |
| RFC-003 | Reasoning Interface | Draft |
| RFC-004 | Node Identity & Plasticity | Draft |
| RFC-005 | Goal System | Draft |
| RFC-006 | Skill Genome | Draft |

## Runtime Verification Status

| Milestone | Focus | Status |
|---|---|---|
| M0 | Autonomic health over Fabric | Green |
| M1 | Memory Fabric + RFC-003 Context Preparation | Green |
| M2 | Task Auction | Green |
| M3 | Values as Gravity | Green |
| M4 | Skill Genome + Plasticity signal | Green |

Reports are protocol-level evidence. They avoid private hostnames, IP
addresses, hardware inventory, operator paths, and model preferences.

---

## Origin

This protocol emerged from the practical experience of designing and building a personal agentic AI system, and repeatedly hitting the same architectural wall: a single large model, however capable, is not the right center of gravity for a system meant to reason, remember, act, and hold values all at once.

The practical problems encountered while building that system revealed a deeper architectural question:

*What is the right operating system for cooperative intelligence?*

CAS Fabric Protocol is the answer we are building together.

---

## Contributing

Read [CONTRIBUTING.md](./CONTRIBUTING.md) and [PRINCIPLES.md](./PRINCIPLES.md) first.

Every proposal must explain the problem it solves, the CAS principle it follows, and include compatibility considerations.

The protocol is stable by design. Innovation belongs in implementations.

---

## License

MIT License — see [LICENSE](./LICENSE)
