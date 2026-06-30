# RFC-001 — Autonomic Layer

| Field | Value |
|---|---|
| RFC | 001 |
| Title | Autonomic Layer |
| Status | Draft |
| Version | 0.1 |

---

## Problem

Every cooperative system requires infrastructure that simply runs — health monitoring, routing, logging, synchronization, discovery.

If this infrastructure requires conscious reasoning to operate, it will compete for the same computational resources as actual intelligence work.

---

## Motivation

The biological autonomic nervous system controls heartbeat, breathing, and digestion without involving conscious thought. It has been optimized over hundreds of millions of years for one purpose: keep the organism alive without burdening the reasoning layers.

CAS Fabric needs the same separation.

Infrastructure concerns must be resolved at a layer that requires zero LLM invocations.

---

## Specification

### 1. Definition

The Autonomic Layer is the set of protocol behaviors that must operate continuously, deterministically, and without invoking reasoning nodes.

### 2. Required Autonomic Functions

Every compliant fabric implementation must provide:

**2.1 Health Pulse**

Each node must emit a health signal at a regular interval.

```json
{
  "node_id": "string",
  "timestamp": "ISO8601",
  "status": "healthy | degraded | unavailable",
  "load": 0.0,
  "version": "string"
}
```

The interval is implementation-defined. The schema is protocol-defined.

**2.2 Discovery**

Nodes must be discoverable by capability, not by address.

A node seeking a reasoning partner must be able to query:  
*"Who can do X?"* — not *"Where is node Y?"*

Address-based routing is an implementation detail. Capability-based discovery is a protocol requirement.

**2.3 Routing**

The fabric must route messages to capable nodes without requiring the sender to know the receiver's address.

**2.4 Synchronization**

The fabric must provide a mechanism for nodes to agree on shared state without a central coordinator.

**2.5 Logging**

All messages passing through the fabric must be observable. Observability is not optional — it is how the system learns about itself.

### 3. What the Autonomic Layer Must Not Do

- It must not invoke LLM nodes to resolve routing decisions
- It must not make semantic judgments about message content
- It must not block message delivery while waiting for reasoning
- It must not require human intervention to recover from node failure

### 4. Transport Independence

The Autonomic Layer must expose only four primitives to the layers above:

```
publish(topic, message)
subscribe(topic, handler)
request(capability, payload) → response
reply(request_id, payload)
```

Whether the underlying transport is MQTT, NATS, gRPC, shared memory, or Bluetooth is an implementation detail invisible to all layers above.

---

## Examples

### Minimal health pulse (Python pseudocode)

```python
async def heartbeat(node_id: str, fabric: Fabric):
    while True:
        await fabric.publish("autonomic.health", {
            "node_id": node_id,
            "timestamp": now(),
            "status": "healthy",
            "load": current_load()
        })
        await sleep(interval)
```

### Capability-based discovery

```python
# Wrong — address-based
node = fabric.get_node("192.168.1.42")

# Correct — capability-based  
node = await fabric.discover(capability="text.summarize")
```

---

## Open Questions

- What is the minimum heartbeat interval before a node is considered unavailable?
- Should the Autonomic Layer handle message persistence, or is that the Memory Fabric's responsibility?
- How should discovery handle nodes that partially satisfy a capability requirement?

---

## CAS Test

| Question | Answer |
|---|---|
| Is it local? | Yes — health and routing decisions use local information |
| Is it composable? | Yes — any node can participate without modifying others |
| Is it adaptive? | Yes — routing adapts to node availability without protocol change |
| Is it emergent? | Yes — system topology emerges from discovery, not configuration |
| Is it implementation-independent? | Yes — only the four primitives and schemas are specified |
