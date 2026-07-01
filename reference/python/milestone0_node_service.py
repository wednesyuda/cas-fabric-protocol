"""
Long-running Milestone 0 node service.

Runs one CAS Fabric node against the live NATS Fabric and keeps the
Autonomic Layer alive by emitting health pulses continuously.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from fabric_nats import NATSFabric
from node_core import Node, NodeIdentity, SkillMetrics


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    fabric = NATSFabric()
    await fabric.connect()

    node = Node(
        fabric,
        identity=NodeIdentity(
            hardware_class="dell-precision-5820-p2000",
            cpu_cores=4,
            ram_gb=32.0,
            has_gpu=True,
            fabric_version="0.1",
        ),
        health_interval_s=5.0,
        retention_check_interval_s=30.0,
    )

    await node.start()
    skill = await node.load_skill("text.summarize", version="v1")
    skill.metrics = SkillMetrics(
        utilization_rate=0.8,
        recency_score=1.0,
        memory_footprint_gb=0.1,
        energy_cost=0.1,
        ecosystem_demand=0.6,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    logging.info("Milestone 0 node started: node_id=%s", node.identity.node_id)
    await stop_event.wait()

    logging.info("Milestone 0 node stopping")
    await node.stop()
    await fabric.close()


if __name__ == "__main__":
    asyncio.run(main())
