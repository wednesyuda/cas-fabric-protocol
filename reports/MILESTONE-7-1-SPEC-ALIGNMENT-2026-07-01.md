# Milestone 7.1 — Spec Alignment Patch

Date: 2026-07-01

Status: Green

## Purpose

Milestone 7.1 aligns the public RFC text and run documentation with the
reference runtime that reached M7 compliance.

This is a documentation/spec patch. It does not change the verified runtime
behavior.

## Changes

- RFC-002 now clarifies that Values Memory must be runtime-configurable in
  production, while reference implementations may ship seed values for canaries.
- RFC-003 now documents executor skill mapping as an implementation boundary and
  recommends a registry for production deployments.
- RFC-005 now describes Goal Store semantics, lifecycle history, Goal capability
  behavior, failure semantics, and the relationship between Goal state, Task
  Auction, and Reflection state.
- README and the Python reference README now explain how to run the compliance
  runner from a clean clone without embedding private deployment details.
- A small Makefile provides `compile`, `schemas`, and `compliance` targets.

## Reference Boundaries

The public protocol repository intentionally keeps deployment-specific details
out of the RFCs and reports.

The Python runtime remains a minimal reference implementation:

- seed Values policies are defaults, not protocol law
- demo executor mappings are sufficient for canaries, not a full production
  registry
- local JSON Goal/Reflection stores are acceptable for reference verification,
  while production deployments should use the Memory Fabric or equivalent
  auditable storage

## Verification

Static verification after this patch:

- Python reference files compile
- JSON schemas parse
- sensitive deployment detail scan passes

Runtime compliance remains covered by M7 and can be rerun with:

```bash
make compliance
```
