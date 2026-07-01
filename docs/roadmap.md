# Roadmap

## Current State

The protocol is in draft, with a private reference runtime used to verify
the coherence of the RFC contracts. Runtime reports in this repository are
generalized and intentionally omit deployment-specific details.

| RFC | Title | Status |
|---|---|---|
| RFC-000 | Design Philosophy & Constitution | Draft |
| RFC-001 | Autonomic Layer | Draft / runtime verified |
| RFC-002 | Memory Fabric | Draft / runtime verified |
| RFC-003 | Reasoning Interface + Task Auction | Draft / runtime verified |
| RFC-004 | Node Identity & Plasticity | Draft / partially runtime verified |
| RFC-005 | Goal System | Draft |
| RFC-006 | Skill Genome | Draft / partially runtime verified |

## Verified Milestones

| Milestone | Focus | Status |
|---|---|---|
| M0 | Autonomic health over Fabric | Green |
| M1 | Memory Fabric + RFC-003 Context Preparation | Green |
| M2 | Task Auction | Green |
| M3 | Values as Gravity | Green |
| M4 | Skill Genome + Plasticity signal | Green |
| M4.5 | Spec and schema alignment | Green |
| M5 | Goal System | Green |
| M6 | Reflection / Adaptive Scoring | Green |
| M7 | Compliance runner + seed stabilization | Green |

---

## Near Term

**Compliance Test Suite**  
Expand the runtime compliance runner into an implementation-independent
test suite that other language implementations can reuse.

---

## Medium Term

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
