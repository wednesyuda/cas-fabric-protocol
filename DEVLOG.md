# CAS Fabric Protocol - Development Log

> Public development log for protocol-level decisions and verification notes.
> Keep environment-specific hostnames, IP addresses, hardware inventory, usernames,
> and private deployment details out of this file.

---

## [2026-06-30] - Foundation & Architecture

### Repository Scope

`cas-fabric-protocol` defines the protocol contracts and reference runtime
needed to explore a distributed cognitive substrate:

- RFC-000: Design Philosophy
- RFC-001: Autonomic Layer
- RFC-002: Memory Fabric
- RFC-003: Reasoning Interface and Task Auction
- RFC-004: Node Identity and Plasticity
- RFC-005: Goal System
- RFC-006: Skill Genome

### Architecture Decisions

- Three-layer model: Autonomic, Limbic/Memory Fabric, and Neocortex/reasoning nodes.
- Values as Gravity: values are embedded into Memory Fabric behavior, not modeled as a separate persona agent.
- Skill as State: node identity remains stable while skills are transient.
- Task Auction: coordination is expressed as broadcast, proposal, and assignment.
- Forgetting as Adaptation: retention score determines when skills can be released.
- Fast Path / Slow Path: memory relevance is computed without LLM invocation unless confidence requires escalation.
- High-confidence action boundary: action-taking paths require explicit confidence and constraint checks.

### Implementation Direction

- Reference implementation language: Python.
- Fabric transport used by the reference runtime: NATS.
- Memory substrate used by the reference runtime: vector store with HTTP API compatibility.
- Local model server used by the reference runtime: configurable HTTP inference endpoint.

All concrete endpoints, model names, paths, and host details must be supplied by
deployment configuration, not hardcoded into the protocol.

---

## [2026-07-01] - Production Verification Artifacts

### Milestone Status

- Milestone 0: green runtime canary for one node, one skill, health pulse over Fabric.
- Milestone 1: green canonical runtime canary for Memory Fabric plus RFC-003 context preparation.
- Milestone 2: green runtime canary for Task Auction proposal and assignment flow.

### Public Artifact Policy

Reports in this repository are intentionally generalized. They preserve:

- protocol contracts verified,
- runtime components involved,
- canary pass/fail outcomes,
- implementation lessons relevant to the protocol.

They omit:

- private hostnames,
- private IP addresses,
- hardware inventory,
- usernames and absolute private paths,
- locally preferred model names unless the protocol requires them.

The private deployment may keep more detailed operator notes outside this public
repository.
