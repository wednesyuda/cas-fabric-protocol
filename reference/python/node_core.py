"""
node_core.py — CAS Fabric Protocol Reference Implementation

Implements the contracts defined in:
  RFC-001 — Autonomic Layer (health pulse, four fabric primitives)
  RFC-004 — Node Identity & Plasticity (identity, skill manifest, retention)

This is a REFERENCE implementation, not the only valid one (RFC-000,
Principle 3: define contracts, never implementations). It exists to
prove the specification is implementable and to give other
implementors a concrete starting point.

Milestone 0 scope:
  - Node identity (RFC-004 §1)
  - Skill lifecycle: AVAILABLE -> LOADING -> ACTIVE -> RELEASING (RFC-004 §3)
  - Retention score calculation (RFC-004 §4)
  - Health pulse emission (RFC-001 §2.1)
  - Four fabric primitives as an interface (RFC-001 §4) —
    backed by an in-memory fabric for now. A real NATS-backed
    fabric implementation will satisfy the same interface.

Out of scope for Milestone 0 (later milestones):
  - Real message bus (NATS) — see fabric.py (Milestone 1)
  - Real vector store (Qdrant) — see memory_fabric.py (Milestone 1)
  - Task Auction (RFC-003) — see coordinator.py (Milestone 2)
  - Values Fabric (RFC-002 §5) — see values_fabric.py (Milestone 3)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional


# ──────────────────────────────────────────────────────────────────
# RFC-001 §2.1 — Health Pulse schema
# ──────────────────────────────────────────────────────────────────

class NodeStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


def iso_now() -> str:
    """Return an RFC-3339/ISO8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class HealthPulse:
    """RFC-001 §2.1 — emitted at a regular interval by every node."""
    node_id: str
    timestamp: str
    status: NodeStatus
    load: float
    version: str
    active_skill_count: int = 0
    accepting_goals: bool = True

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "load": self.load,
            "version": self.version,
            "active_skill_count": self.active_skill_count,
            "accepting_goals": self.accepting_goals,
        }


# ──────────────────────────────────────────────────────────────────
# RFC-004 §3 — Skill Lifecycle
# ──────────────────────────────────────────────────────────────────

class SkillState(str, Enum):
    AVAILABLE = "available"   # exists in Genome, not loaded here
    LOADING = "loading"       # being acquired
    ACTIVE = "active"         # loaded, usable
    RELEASING = "releasing"   # being unloaded


@dataclass
class SkillMetrics:
    """Inputs to the RFC-004 §4 retention score formula."""
    utilization_rate: float = 0.0     # how often used, last N days, [0, 1]
    recency_score: float = 1.0        # decays as time since last use grows
    memory_footprint_gb: float = 0.0  # RAM consumed while active
    energy_cost: float = 0.0          # normalized power draw, [0, 1]
    ecosystem_demand: float = 0.0     # from Skill Genome (RFC-006 §7), [0, 1]


@dataclass
class ActiveSkill:
    """RFC-004 §2 — one entry in a node's Skill Manifest."""
    skill_id: str
    version: str
    state: SkillState = SkillState.LOADING
    loaded_at: str = field(default_factory=iso_now)
    last_used_at: float = field(default_factory=time.time)
    metrics: SkillMetrics = field(default_factory=SkillMetrics)
    latency_p50_ms: int = 0
    latency_p95_ms: int = 0

    def touch(self) -> None:
        """Mark as used now — call this whenever the skill handles a task."""
        self.last_used_at = time.time()


# Default weights for the retention score formula (RFC-004 §4).
# Implementation-defined per the RFC — these are the reference defaults.
RETENTION_WEIGHTS = {
    "w1_utilization": 0.35,
    "w2_recency": 0.20,
    "w3_memory_footprint": 0.20,
    "w4_energy_cost": 0.10,
    "w5_ecosystem_demand": 0.15,
}

# RFC-004 §4 — recommended default release threshold
DEFAULT_RELEASE_THRESHOLD = 0.2


def compute_retention_score(
    metrics: SkillMetrics,
    weights: dict = RETENTION_WEIGHTS,
) -> float:
    """
    RFC-004 §4:

        retention_score =
              w1 * utilization_rate
            + w2 * recency_score
            - w3 * memory_footprint
            - w4 * energy_cost
            + w5 * ecosystem_demand

    memory_footprint and energy_cost are penalties (subtracted).
    Result is not strictly bounded to [0, 1] by construction; callers
    compare against a threshold, not an absolute scale.
    """
    return (
        weights["w1_utilization"] * metrics.utilization_rate
        + weights["w2_recency"] * metrics.recency_score
        - weights["w3_memory_footprint"] * metrics.memory_footprint_gb
        - weights["w4_energy_cost"] * metrics.energy_cost
        + weights["w5_ecosystem_demand"] * metrics.ecosystem_demand
    )


# ──────────────────────────────────────────────────────────────────
# RFC-001 §4 — Fabric primitives (interface)
# ──────────────────────────────────────────────────────────────────

class Fabric:
    """
    RFC-001 §4 (v0.2) — the three primitives any layer above the
    Autonomic Layer is allowed to depend on:

        publish(topic, message)
        subscribe(topic, handler)
        request(capability, payload) -> response

    There is no standalone reply(request_id, payload) primitive.
    An earlier draft had one; it was removed after Milestone 0
    verification showed it doesn't match how real transports like
    NATS answer requests (see RFC-001 §4 revision note for the
    full rationale).

    The answering side works like this instead: a handler
    subscribed to a capability topic receives the request payload
    PLUS a `respond` callback. Calling that callback fulfills the
    original request() call on the caller's side. This mirrors
    NATS's msg.respond() pattern even in this in-memory
    implementation — so code written against this Fabric needs
    zero changes to work against NATSFabric (see fabric_nats.py).

    This is an in-memory reference implementation for Milestone 0.
    A NATS-backed implementation (Milestone 1) satisfies the exact
    same interface — nothing above this layer should need to
    change when the transport changes (RFC-000, Principle 3).
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable]] = {}

    async def publish(self, topic: str, message: dict) -> None:
        """
        Delivers message to all topic subscribers wrapped in the
        standard envelope: {"payload": message}

        This matches NATSFabric's delivery shape — pub/sub handlers
        always receive {"payload": ...} regardless of which Fabric
        implementation is underneath. Handlers do NOT receive the
        raw message dict directly.
        """
        envelope = {"payload": message}
        for handler in self._subscribers.get(topic, []):
            asyncio.create_task(self._safe_call(handler, envelope))

    def subscribe(self, topic: str, handler: Callable[[dict], Any]) -> None:
        self._subscribers.setdefault(topic, []).append(handler)

    async def request(
        self, capability: str, payload: dict, timeout: float = 5.0
    ) -> Optional[dict]:
        """
        Capability-based request (RFC-001 §2.2) — NOT address-based.
        Callers ask "who can do X", never "where is node Y".

        Handlers subscribed to f"capability.{capability}" receive
        a message shaped {"payload": ..., "respond": callable}.
        Calling respond(result) fulfills this future. This is the
        in-memory equivalent of NATS's reply-subject mechanism —
        no request_id bookkeeping leaks into the public interface.

        NOTE: delivers directly to handlers rather than going through
        publish(), because publish() adds a {"payload": ...} wrapper
        for standard broadcasts and we must not double-wrap here.
        """
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        def _respond(result: dict) -> None:
            if not future.done():
                future.set_result(result)

        envelope = {"payload": payload, "respond": _respond}
        topic = f"capability.{capability}"
        for handler in self._subscribers.get(topic, []):
            asyncio.create_task(self._safe_call(handler, envelope))

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return None

    @staticmethod
    async def _safe_call(handler: Callable, message: dict) -> None:
        result = handler(message)
        if asyncio.iscoroutine(result):
            await result


# ──────────────────────────────────────────────────────────────────
# RFC-004 §1 — Node Identity
# ──────────────────────────────────────────────────────────────────

@dataclass
class NodeIdentity:
    """
    RFC-004 §1 — permanent for the lifetime of the node.
    Does NOT change when skills are acquired or released.
    """
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=iso_now)
    hardware_class: str = "unspecified"
    cpu_cores: int = 0
    ram_gb: float = 0.0
    has_npu: bool = False
    has_gpu: bool = False
    power_envelope_watts: float = 0.0
    fabric_version: str = "0.1"


# ──────────────────────────────────────────────────────────────────
# The Node itself
# ──────────────────────────────────────────────────────────────────

class Node:
    """
    A CAS Fabric node.

    Identity is stable (RFC-004 §1). Skills are transient (RFC-004 §3).
    This class owns the retention loop (RFC-004 §4) and the health
    pulse loop (RFC-001 §2.1) — both run continuously, both require
    zero reasoning (Autonomic Layer behavior, RFC-001 §1).
    """

    def __init__(
        self,
        fabric: Fabric,
        identity: Optional[NodeIdentity] = None,
        health_interval_s: float = 10.0,
        retention_check_interval_s: float = 60.0,
        release_threshold: float = DEFAULT_RELEASE_THRESHOLD,
    ) -> None:
        self.fabric = fabric
        self.identity = identity or NodeIdentity()
        self.active_skills: dict[str, ActiveSkill] = {}
        self._health_interval_s = health_interval_s
        self._retention_check_interval_s = retention_check_interval_s
        self._release_threshold = release_threshold
        self._running = False
        self._tasks: list[asyncio.Task] = []

    # ── Skill lifecycle (RFC-004 §3) ────────────────────────────

    async def load_skill(
        self, skill_id: str, version: str = "v1"
    ) -> ActiveSkill:
        """
        AVAILABLE -> LOADING -> ACTIVE

        In Milestone 0 this is a stub: no real Skill Genome exists
        yet (RFC-006), so "loading" just means constructing the
        manifest entry. Milestone 1+ will replace the body of this
        method with an actual fetch from the Genome.
        """
        skill = ActiveSkill(skill_id=skill_id, version=version, state=SkillState.LOADING)
        self.active_skills[skill_id] = skill

        # --- placeholder for actual acquisition from Skill Genome (RFC-006) ---
        await asyncio.sleep(0)  # yield point; real impl awaits genome.acquire()
        # ------------------------------------------------------------------

        skill.state = SkillState.ACTIVE
        await self.fabric.publish(
            "node.manifest_updated",
            {"node_id": self.identity.node_id, "skill_id": skill_id, "state": skill.state.value},
        )
        return skill

    async def release_skill(self, skill_id: str, reason: str = "manual") -> None:
        """
        ACTIVE -> RELEASING -> (back to AVAILABLE in the Genome)

        RFC-004 §3 + RFC-006: releasing a skill does not destroy it.
        It returns to the Genome's availability — other nodes can
        always acquire it. This node just no longer carries it.
        """
        skill = self.active_skills.get(skill_id)
        if skill is None:
            return
        skill.state = SkillState.RELEASING
        await self.fabric.publish(
            "node.skill_released",
            {"node_id": self.identity.node_id, "skill_id": skill_id, "reason": reason},
        )
        del self.active_skills[skill_id]

    def skill_manifest(self) -> dict:
        """RFC-004 §2 — current capability advertisement."""
        return {
            "node_id": self.identity.node_id,
            "timestamp": time.time(),
            "active_skills": [
                {
                    "skill_id": s.skill_id,
                    "version": s.version,
                    "latency_p50_ms": s.latency_p50_ms,
                    "latency_p95_ms": s.latency_p95_ms,
                    "loaded_at": s.loaded_at,
                }
                for s in self.active_skills.values()
                if s.state == SkillState.ACTIVE
            ],
        }

    # ── Retention loop (RFC-004 §4 — "forgetting as adaptation") ─

    async def _retention_loop(self) -> None:
        while self._running:
            for skill_id, skill in list(self.active_skills.items()):
                if skill.state != SkillState.ACTIVE:
                    continue
                score = compute_retention_score(skill.metrics)
                if score < self._release_threshold:
                    await self.release_skill(
                        skill_id, reason="retention_score_below_threshold"
                    )
            await asyncio.sleep(self._retention_check_interval_s)

    # ── Health pulse loop (RFC-001 §2.1) ──────────────────────────

    async def _health_loop(self) -> None:
        while self._running:
            pulse = HealthPulse(
                node_id=self.identity.node_id,
                timestamp=iso_now(),
                status=NodeStatus.HEALTHY,
                load=self._current_load(),
                version=self.identity.fabric_version,
                active_skill_count=len(
                    [s for s in self.active_skills.values() if s.state == SkillState.ACTIVE]
                ),
            )
            await self.fabric.publish("autonomic.health", pulse.to_dict())
            await asyncio.sleep(self._health_interval_s)

    def _current_load(self) -> float:
        """
        Placeholder load metric for Milestone 0.
        Real implementation should read actual CPU/GPU utilization.
        """
        return min(1.0, len(self.active_skills) * 0.15)

    # ── Lifecycle control ─────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        self._tasks = [
            asyncio.create_task(self._health_loop()),
            asyncio.create_task(self._retention_loop()),
        ]

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)


# ──────────────────────────────────────────────────────────────────
# Milestone 0 demo — proves the loop is alive
# ──────────────────────────────────────────────────────────────────

async def _demo() -> None:
    """
    Minimal end-to-end proof for Milestone 0:
      1. A node comes up with an identity
      2. It loads a skill
      3. It emits a health pulse carrying that skill count
      4. A low-retention skill gets released automatically

    Run: python node_core.py
    """
    fabric = Fabric()

    received_pulses: list[dict] = []
    fabric.subscribe("autonomic.health", lambda msg: received_pulses.append(msg["payload"]))

    node = Node(
        fabric,
        identity=NodeIdentity(
            hardware_class="generic-reference-node",
            cpu_cores=4,
            ram_gb=32.0,
            has_gpu=True,
            fabric_version="0.1",
        ),
        health_interval_s=1.0,
        retention_check_interval_s=2.0,
    )

    print(f"Node identity: {node.identity.node_id}")
    print(f"Hardware: {node.identity.hardware_class}\n")

    await node.start()

    skill = await node.load_skill("text.summarize", version="v1")
    print(f"Loaded skill: {skill.skill_id} -> state={skill.state.value}")

    # Simulate a skill nobody is using — should get released by the
    # retention loop because its metrics score below threshold.
    stale_skill = await node.load_skill("vision.ocr", version="v1")
    stale_skill.metrics = SkillMetrics(
        utilization_rate=0.0,
        recency_score=0.05,
        memory_footprint_gb=2.0,
        energy_cost=0.6,
        ecosystem_demand=0.1,
    )
    score = compute_retention_score(stale_skill.metrics)
    print(f"Stale skill retention score: {score:.3f} "
          f"(threshold={DEFAULT_RELEASE_THRESHOLD}) -> "
          f"{'will be released' if score < DEFAULT_RELEASE_THRESHOLD else 'will be kept'}\n")

    print("Manifest before retention cycle:")
    for s in node.skill_manifest()["active_skills"]:
        print(f"  - {s['skill_id']}")

    await asyncio.sleep(2.5)  # let one retention cycle run

    print("\nManifest after retention cycle:")
    for s in node.skill_manifest()["active_skills"]:
        print(f"  - {s['skill_id']}")

    await asyncio.sleep(1.2)  # let one more health pulse land
    await node.stop()

    print(f"\nHealth pulses received: {len(received_pulses)}")
    if received_pulses:
        print(f"Last pulse: {received_pulses[-1]}")


if __name__ == "__main__":
    asyncio.run(_demo())
