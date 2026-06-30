# Roadmap

## Current State

The protocol is in early draft. The foundation is being laid.

| RFC | Title | Status |
|---|---|---|
| RFC-000 | Design Philosophy & Constitution | Draft |
| RFC-001 | Autonomic Layer | Draft |
| RFC-002 | Memory Fabric | Draft |
| RFC-003 | Reasoning Interface | Draft |
| RFC-004 | Node Identity & Plasticity | Draft |
| RFC-005 | Goal System | Stub
| RFC-006 | Skill Genome | Draft | |

---

## Near Term

**RFC-004 — Node Identity & Capability**  
Define how nodes declare what they can do and how well they do it.

**RFC-005 — Goal System**  
Define persistent objectives that exist independently of prompts.

**JSON Schemas**  
Formalize the message schemas referenced in the existing RFCs.

**Reference Examples**  
Minimal working examples in Python and TypeScript demonstrating the Memory Fabric interface.

---

## Medium Term

**RFC-006 — Scheduling**  
Capability-aware task routing. Which node is most suitable — not just which is available.

**RFC-007 — Reflection**  
How the system evaluates its own performance and adjusts behavior without retraining.

**RFC-008 — Evolution**  
How node architectures can be replaced and upgraded within a running ecosystem.

---

## Long Term

**Reference Implementation**  
A complete, minimal implementation of the full protocol in one language. Not the only valid implementation — a proof that the specification is coherent.

**Compliance Test Suite**  
A set of tests that any implementation can run to verify protocol compliance.

**Ecosystem**  
Separate repositories for community implementations: `cas-fabric-python`, `cas-fabric-go`, `cas-fabric-typescript`.

---

## What Will Not Change

The six principles in PRINCIPLES.md.  
The CAS Test.  
The Values Fabric Requirement.  
The three-layer architectural model.

These are the foundation. Everything else is negotiable.
