# Memory Fabric Canonical Integration - 2026-07-01

## Scope

This report records the public integration result for the canonical RFC-002 Memory Fabric reference implementation. Private deployment paths, hostnames, IP addresses, and hardware details are intentionally omitted.

## Integrated Components

- `reference/python/memory_fabric.py`
- `reference/python/canonical_memory_node_service.py`
- `reference/python/context_preparation_service.py`
- `reference/python/verify_milestone1_canonical_runtime.py`

The wrapper delegates memory behavior to the canonical Memory Fabric implementation while preserving the response contract used by runtime canaries.

## Runtime Dependencies

The reference runtime expects:

- Fabric transport endpoint configured by `CAS_NATS_URL`
- Vector store endpoint configured by `CAS_QDRANT_URL`
- Embedding endpoint configured by `CAS_OLLAMA_URL`
- Embedding model configured by `CAS_EMBED_MODEL`

The verified embedding dimensionality is 768 for the configured embedding model in the private runtime.

## Verification

The canonical Memory Fabric path passed:

- memory write
- memory query
- values signature generation
- RFC-003 context preparation
- reasoning request envelope consumption

## Verdict

Canonical Memory Fabric integration: green at protocol level, with deployment-specific details externalized to configuration.
