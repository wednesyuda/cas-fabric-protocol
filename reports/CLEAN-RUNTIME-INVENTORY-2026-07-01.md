# Clean Runtime Inventory - 2026-07-01

## Scope

This report records the public, protocol-level shape of a clean CAS Fabric runtime after Milestone 0-2 verification. Environment-specific hostnames, IP addresses, hardware details, usernames, and private filesystem paths are intentionally omitted.

## Canonical Runtime Shape

Active reference services:

- Autonomic node
- Canonical Memory Fabric node
- Context Preparation node
- Reasoning node
- Task Coordinator node
- Auction worker for memory capability
- Auction worker for reasoning capability

Active reference files are under `reference/python/`. Deployment templates are under `deploy/systemd/user/`.

## Transport

The verified runtime uses one Fabric message bus instance for CAS Fabric traffic. Reference code targets NATS through the RFC-001 Fabric interface, but the protocol contract remains transport-shaped rather than deployment-shaped.

## Configuration Policy

Runtime endpoints are configured with environment variables:

- `CAS_NATS_URL`
- `CAS_QDRANT_URL`
- `CAS_OLLAMA_URL`
- `CAS_EMBED_MODEL`
- `CAS_REASONING_MODEL`

No private hostnames, private IP addresses, or operator-specific paths are required by the protocol.

## Verification

Runtime canaries passed for:

- Milestone 0 health pulse over Fabric
- Milestone 1 Memory Fabric plus RFC-003 context preparation
- Milestone 2 Task Auction proposal, assignment, and execution flow

## Verdict

Clean runtime inventory: green, slimmed, and protocol-generalized.
