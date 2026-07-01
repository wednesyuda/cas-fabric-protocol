"""
fabric_nats.py — NATS-backed Fabric (RFC-001 §4)

Replaces the in-memory Fabric from node_core.py with a real
message bus, WITHOUT changing the Fabric interface those classes
depend on. This is the proof of RFC-000 Principle 3 in practice:
"define contracts, never implementations."

If Node, ActiveSkill, or any other class in node_core.py needed
to change to support this file, the interface boundary in
Milestone 0 was drawn wrong. They do not need to change.

Requires:
    pip install nats-py

Requires a running NATS server. Default: nats://localhost:4222
Install: https://docs.nats.io/running-a-nats-service/introduction/installation

    # macOS
    brew install nats-server
    nats-server

    # Linux (binary)
    curl -sf https://binaries.nats.dev/nats-io/nats-server/v2@latest | sh
    ./nats-server
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Optional

import nats
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg
from nats.errors import TimeoutError as NATSTimeoutError

logger = logging.getLogger("cas_fabric.nats")


class NATSFabric:
    """
    NATS-backed implementation of the three RFC-001 §4 (v0.2) primitives:

        publish(topic, message)
        subscribe(topic, handler)
        request(capability, payload) -> response

    Same method names, same call shape as the in-memory Fabric in
    node_core.py — any code written against that interface (Node,
    the Milestone 0 demo, future Memory Fabric / Reasoning code)
    works unmodified against this class.

    On answering requests: RFC-001 §4 was revised after Milestone 0
    verification found that a standalone reply(request_id, payload)
    primitive doesn't match how real transports answer requests.
    NATS answers synchronously inside the handler, via a reply
    subject it sets up automatically — there's no "look up
    request_id later" step.

    To keep handler code portable across Fabric implementations,
    BOTH this class and the in-memory Fabric deliver requests to
    subscribed handlers in the same shape:

        {"payload": <the request payload>, "respond": <callable>}

    A handler calls respond(result_dict) to answer. Underneath,
    the in-memory Fabric resolves a local Future; this class calls
    msg.respond() on the original NATS message. The handler itself
    doesn't need to know which one it's talking to.

    Design notes:
      - Topics map directly to NATS subjects. No translation needed —
        this is one of the reasons NATS fits RFC-001 §4 so cleanly.
      - request() uses NATS's native request-reply pattern instead of
        manual asyncio.Future bookkeeping — NATS already solves
        request/response correlation at the transport layer.
      - JSON is used for payload encoding. The protocol itself
        (RFC-001, message.schema.json) does not mandate JSON — this
        is an implementation choice, swappable for msgpack/protobuf
        later without touching RFC text.
    """

    def __init__(self, servers: str | list[str] = "nats://localhost:4222") -> None:
        self._servers = servers
        self._nc: Optional[NATSClient] = None
        self._subscriptions: list = []
        self._closing = False

    async def connect(self, connect_timeout: float = 5.0) -> None:
        """
        Raises on initial connection failure — does NOT silently hang.

        nats-py's own connect_timeout/max_reconnect_attempts parameters
        govern reconnect behavior AFTER a successful first connection,
        but were found (empirically, while building this) to NOT
        reliably bound the time spent on the very first connection
        attempt when max_reconnect_attempts=-1 is set. So we enforce
        the deadline ourselves with asyncio.wait_for instead of trusting
        the library to do it.

        Raises asyncio.TimeoutError if no server responds within
        connect_timeout seconds.
        """
        self._nc = await asyncio.wait_for(
            nats.connect(
                servers=self._servers,
                reconnect_time_wait=2,
                max_reconnect_attempts=-1,  # retry forever, but only AFTER first success
                error_cb=self._on_error,
                disconnected_cb=self._on_disconnected,
                reconnected_cb=self._on_reconnected,
            ),
            timeout=connect_timeout,
        )
        self._closing = False
        logger.info(f"Connected to NATS at {self._servers}")

    async def close(self) -> None:
        if self._nc and not self._nc.is_closed:
            self._closing = True
            await self._nc.drain()
            logger.info("Disconnected from NATS")

    # ── RFC-001 §4 (v0.2) primitives ────────────────────────────

    async def publish(self, topic: str, message: dict) -> None:
        """Fire-and-forget broadcast. No reply expected."""
        if self._nc is None:
            raise RuntimeError("NATSFabric.connect() must be called first")
        payload = json.dumps(message).encode("utf-8")
        await self._nc.publish(topic, payload)

    def subscribe(self, topic: str, handler: Callable[[dict], Any]) -> None:
        """
        Registers a handler for a topic.

        If the underlying NATS message carries a reply subject (i.e.
        it came from a request() call on the other end), the handler
        receives {"payload": ..., "respond": callable} — calling
        respond(result) answers the request. Plain pub/sub messages
        (no reply subject) are delivered as {"payload": ...} with no
        respond key, matching the in-memory Fabric's behavior.

        Because nats-py subscription is itself async (it needs to
        await nc.subscribe(...)), and this method's signature in
        RFC-001 §4 / node_core.py is synchronous, the actual
        subscription is scheduled as a background task. The handler
        will start receiving messages shortly after this call
        returns — callers needing a hard guarantee of "subscribed
        before returning" should use subscribe_async() instead.
        """
        asyncio.create_task(self._subscribe_async(topic, handler))

    async def subscribe_async(self, topic: str, handler: Callable[[dict], Any]) -> None:
        """Same as subscribe(), but awaitable — guarantees subscription
        is active before returning. Prefer this in new code; subscribe()
        exists for drop-in compatibility with the in-memory Fabric's
        synchronous signature."""
        await self._subscribe_async(topic, handler)

    async def _subscribe_async(self, topic: str, handler: Callable[[dict], Any]) -> None:
        if self._nc is None:
            raise RuntimeError("NATSFabric.connect() must be called first")

        async def _on_message(msg: Msg) -> None:
            try:
                data = json.loads(msg.data.decode("utf-8"))
            except json.JSONDecodeError:
                logger.warning(f"Dropped malformed message on '{topic}'")
                return

            envelope: dict = {"payload": data}
            if msg.reply:
                async def _respond(result: dict, _msg=msg) -> None:
                    await _msg.respond(json.dumps(result).encode("utf-8"))
                envelope["respond"] = _respond

            result = handler(envelope)
            if asyncio.iscoroutine(result):
                await result

        sub = await self._nc.subscribe(topic, cb=_on_message)
        self._subscriptions.append(sub)

    async def request(
        self, capability: str, payload: dict, timeout: float = 5.0
    ) -> Optional[dict]:
        """
        Capability-based request (RFC-001 §2.2) — callers ask
        "who can do X", never "where is node Y". The NATS subject
        IS the capability name; whichever node subscribed to
        `capability.{capability}` and calls the respond() callback
        delivered in its handler's envelope will answer.

        Returns None on timeout, matching the in-memory Fabric's
        behavior so callers don't need to branch on which Fabric
        implementation they're using.
        """
        if self._nc is None:
            raise RuntimeError("NATSFabric.connect() must be called first")

        subject = f"capability.{capability}"
        data = json.dumps(payload).encode("utf-8")
        try:
            response: Msg = await self._nc.request(subject, data, timeout=timeout)
            return json.loads(response.data.decode("utf-8"))
        except NATSTimeoutError:
            return None

    # ── connection lifecycle callbacks ──────────────────────────

    async def _on_error(self, e: Exception) -> None:
        logger.error(f"NATS error: {e}")

    async def _on_disconnected(self) -> None:
        if self._closing:
            logger.info("NATS disconnected during intentional close")
            return
        logger.warning("NATS disconnected — will retry per reconnect policy")

    async def _on_reconnected(self) -> None:
        logger.info("NATS reconnected")


# ──────────────────────────────────────────────────────────────────
# Usage example — run node_core.py's Node against a real NATS server
# ──────────────────────────────────────────────────────────────────

async def _demo() -> None:
    """
    Requires a running NATS server (see module docstring for install).

    Run:
        nats-server &
        python3 fabric_nats.py
    """
    import sys
    import os

    sys.path.insert(0, os.path.dirname(__file__))
    from node_core import Node, NodeIdentity, SkillMetrics, compute_retention_score, DEFAULT_RELEASE_THRESHOLD

    fabric = NATSFabric()
    try:
        await fabric.connect()
    except asyncio.TimeoutError:
        print("Could not connect to NATS server: connection timed out.")
        print("Start one first: nats-server")
        return
    except Exception as e:
        print(f"Could not connect to NATS server: {e}")
        print("Start one first: nats-server")
        return

    received_pulses: list[dict] = []
    await fabric.subscribe_async(
        "autonomic.health",
        # handlers receive {"payload": <message>, "respond"?: callable}
        # — unpack the payload for pub/sub messages (no respond key)
        lambda msg: received_pulses.append(msg["payload"])
    )

    node = Node(
        fabric,  # <-- the only line that changed from the Milestone 0 demo
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
    print("Fabric: NATS (real message bus)\n")

    await node.start()

    skill = await node.load_skill("text.summarize", version="v1")
    print(f"Loaded skill: {skill.skill_id} -> state={skill.state.value}")

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

    await asyncio.sleep(2.5)

    print("Manifest after retention cycle:")
    for s in node.skill_manifest()["active_skills"]:
        print(f"  - {s['skill_id']}")

    await asyncio.sleep(1.5)
    await node.stop()
    await fabric.close()

    print(f"\nHealth pulses received over real NATS: {len(received_pulses)}")
    if received_pulses:
        print(f"Last pulse: {received_pulses[-1]}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    asyncio.run(_demo())
