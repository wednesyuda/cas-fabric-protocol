# Reference Implementation — Python

This is **a** reference implementation, not **the** implementation.

Per RFC-000 Principle 3 (define contracts, never implementations), nothing here is required. It exists to prove the specification is implementable and to give other implementors a concrete starting point.

---

## Milestone 0 — `node_core.py`

**Implements:**
- RFC-001 §2.1 — Health Pulse
- RFC-001 §4 — Four fabric primitives (`publish`, `subscribe`, `request`, `reply`), backed by an in-memory fabric
- RFC-004 §1 — Node Identity (stable)
- RFC-004 §3 — Skill Lifecycle (`AVAILABLE → LOADING → ACTIVE → RELEASING`)
- RFC-004 §4 — Retention Score and automatic skill release ("forgetting as adaptation")

**Deliberately stubbed for later milestones:**
- Real message bus (NATS) — Milestone 1
- Real vector store (Qdrant) for Memory Fabric — Milestone 1
- Skill Genome acquisition (RFC-006) — currently `load_skill()` is a placeholder
- Task Auction (RFC-003) — Milestone 2
- Values Fabric (RFC-002 §5) — Milestone 3

### Run it

```bash
python3 node_core.py
```

### What the demo proves

A node comes up with a stable identity, loads two skills, and the retention loop automatically releases the skill whose computed retention score falls below threshold — without any human or LLM call telling it to. Meanwhile the health pulse keeps emitting on its own interval, untouched by any of this.

This is the smallest possible proof that the Autonomic Layer (RFC-001) and Plasticity model (RFC-004) can run as separate, non-reasoning loops — the architectural claim at the center of this protocol.

### Design notes for contributors

- `Fabric` is intentionally swappable. Nothing in `Node` should need to change when this becomes a NATS-backed implementation — only `Fabric`'s internals change. If a future change to `Node` requires touching `Fabric`'s internals, that's a sign the interface boundary was drawn wrong.
- `RETENTION_WEIGHTS` are reference defaults, not protocol-mandated values. RFC-004 §4 leaves weight tuning to implementors.
- `load_skill()` currently has no real Genome to talk to (RFC-006 is spec-only so far). The placeholder comment marks exactly where that integration point goes.

---

## Milestone 0 (continued) — `fabric_nats.py`

Replaces the in-memory `Fabric` with a real NATS-backed implementation. **This is the proof that the interface design from `node_core.py` actually holds** — `Node`, `ActiveSkill`, and everything else in `node_core.py` needed zero changes to run against a real message bus instead of an in-process stub.

### Setup

```bash
pip install nats-py

# Install and run a NATS server (not included — separate binary)
# macOS:   brew install nats-server && nats-server
# Linux:   curl -sf https://binaries.nats.dev/nats-io/nats-server/v2@latest | sh
#          ./nats-server
```

### Run it

```bash
nats-server &          # start the message bus
python3 fabric_nats.py # run the same Milestone 0 demo, over real NATS
```

### What changed from the in-memory version, and why

| Concern | In-memory `Fabric` | `NATSFabric` |
|---|---|---|
| `publish`/`subscribe` | Python dict of callbacks | Real NATS subjects |
| `request`/`response` | Manual `asyncio.Future` bookkeeping | NATS's native request-reply |
| Connection failure | N/A (nothing to connect to) | Must fail fast, not hang — see note below |

### A real bug found during verification — and why it's documented, not hidden

While testing this against a deliberately-absent NATS server (to verify graceful failure), the first version of `connect()` **hung indefinitely** instead of raising an error. `nats-py`'s `max_reconnect_attempts=-1` setting (which we want for long-term resilience — RFC-001's Autonomic Layer should keep trying to reconnect) turned out to also suppress failure on the *first* connection attempt, not just reconnects after an established session.

Fix: wrap the initial `nats.connect()` call in `asyncio.wait_for()` with an explicit timeout, rather than trusting the library's own `connect_timeout` parameter to bound the first attempt. Verified: connecting to a non-existent server now fails cleanly in ~5 seconds with a clear message, instead of hanging.

This is left in the code as a comment and in this README because it's a useful warning for anyone else building NATS-backed Autonomic Layer code: **"retry forever" and "fail fast on first attempt" are not automatically compatible settings** — you may need to enforce the boundary yourself.

### Known open question this implementation surfaced

`NATSFabric.reply()` raises `NotImplementedError`. This is intentional, not a TODO.

RFC-001 §4 defines `reply(request_id, payload)` modeled on a pattern where you look up a pending request by ID later. NATS's native request-reply doesn't work that way — you respond via `msg.respond()` *inside the handler that received the request*, using a reply-subject NATS sets up automatically. There's no "look up request_id later" step in idiomatic NATS usage.

This is a genuine mismatch between the protocol's abstract primitive and at least one real transport's idiom. It's filed as an open question against RFC-001 in `fabric_nats.py`'s closing comment block, per `CONTRIBUTING.md`: *"Open Questions exist for a reason — use it."* A `respond_to_request()` static method is provided as the NATS-idiomatic workaround in the meantime.

### Not yet verified

This implementation has been checked against the real `nats-py` library's API surface (method signatures, connection behavior, request/reply semantics) and tested for graceful failure when no server is present. It has also been verified by runtime canaries against a private deployment; deployment-specific hardware details are intentionally not part of the protocol repository.

---

## Full Compliance Runner — `verify_compliance_runtime.py`

The compliance runner is intentionally thin. It executes the milestone canaries
in order and fails as soon as one canary fails:

```bash
python verify_compliance_runtime.py
```

It does not start infrastructure for you. Before running it, start exactly one
message bus and compatible memory/model services for your environment.

Common environment variables:

```bash
CAS_NATS_URL=nats://localhost:4222
CAS_QDRANT_URL=http://localhost:6333
CAS_OLLAMA_URL=http://localhost:11434
CAS_GOAL_STORE_PATH=/tmp/cas-fabric-goals.json
CAS_REFLECTION_STORE_PATH=/tmp/cas-fabric-reflections.json
```

`localhost` values are examples only. Public reports should describe service
classes and verification status, not private addresses, hostnames, hardware, or
operator paths.

### Reference Implementation Boundaries

The reference runtime deliberately keeps several production concerns simple:

- Context preparation ships with seed Values policies so the Values Gravity
  canary can run without an external governance service. RFC-002 requires
  production Values Memory to be configurable and auditable.
- The task coordinator maps a small set of demo skills to callables. RFC-003
  treats executor mapping as an implementation boundary and recommends a
  registry for production deployments.
- Goal and reflection state can be stored in local JSON files. RFC-005
  recommends routing durable production state through the Memory Fabric or an
  equivalent auditable backing store.
