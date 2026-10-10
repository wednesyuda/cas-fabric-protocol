"""Local executors used to prove real NATS auction routing and interruption."""
import asyncio

from auction_worker_node_service import AuctionWorker
from skill_genome import manifests_for_skills


class ProbeWorker(AuctionWorker):
    def __init__(self, node_id, latency, blocking=False):
        super().__init__()
        self.node_id = node_id
        self.skills = ["release.echo"] + (["release.block"] if blocking else [])
        self.skill_manifests = manifests_for_skills(self.skills)
        self.estimated_latency_ms = latency
        self.calls = []
        self.fail_next_echo = False
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.finished = asyncio.Event()

    async def execute_skill(self, skill, intent):
        self.calls.append((skill, intent))
        if skill == "release.echo" and self.fail_next_echo:
            self.fail_next_echo = False
            return {"ok": False, "error": "controlled executor failure"}
        if skill == "release.block":
            self.started.set()
            await self.release.wait()
            self.finished.set()
        return {"ok": True, "output": self.node_id}
