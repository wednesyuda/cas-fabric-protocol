"""
Milestone 2 Auction Worker.

Subscribes to goal.broadcast and proposes its configured skills.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from fabric_nats import NATSFabric


LOGGER = logging.getLogger("cas_fabric.auction_worker")
PROTOCOL_VERSION = "cas-fabric.task-auction.v0.1"


class AuctionWorker:
    def __init__(self) -> None:
        self.fabric = NATSFabric()
        self.node_id = os.environ.get("CAS_WORKER_ID", "worker-unspecified")
        self.skills = [
            skill.strip()
            for skill in os.environ.get("CAS_WORKER_SKILLS", "").split(",")
            if skill.strip()
        ]
        self.estimated_latency_ms = int(os.environ.get("CAS_WORKER_LATENCY_MS", "100"))
        self.current_load = float(os.environ.get("CAS_WORKER_LOAD", "0.1"))

    async def start(self) -> None:
        if not self.skills:
            raise RuntimeError("CAS_WORKER_SKILLS must not be empty")
        await self.fabric.connect()
        await self.fabric.subscribe_async("goal.broadcast", self.handle_goal)
        await self.fabric.subscribe_async(f"goal.assignment.{self.node_id}", self.handle_assignment)
        LOGGER.info("Auction worker ready: node_id=%s skills=%s", self.node_id, self.skills)

    async def handle_goal(self, message: dict) -> None:
        payload = message.get("payload", {})
        required = set(payload.get("required_skills", []))
        offered = sorted(required & set(self.skills))
        if not offered:
            return
        proposal_subject = payload.get("proposal_subject")
        if not proposal_subject:
            return
        await self.fabric.publish(
            proposal_subject,
            {
                "type": "goal.proposal",
                "protocol": PROTOCOL_VERSION,
                "goal_id": payload.get("goal_id"),
                "node_id": self.node_id,
                "skills_offered": offered,
                "estimated_latency_ms": self.estimated_latency_ms,
                "estimated_energy_cost": 0.1,
                "current_load": self.current_load,
                "confidence": 0.99,
            },
        )

    async def handle_assignment(self, message: dict) -> None:
        LOGGER.info("Assignment received: %s", message.get("payload"))

    async def close(self) -> None:
        await self.fabric.close()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    worker = AuctionWorker()
    await worker.start()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()
    await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
