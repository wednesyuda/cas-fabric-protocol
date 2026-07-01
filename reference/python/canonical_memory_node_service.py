"""
Canonical Milestone 1 Memory Node wrapper.

Uses memory_fabric.py as the canonical RFC-002 implementation while
preserving the runtime response contract used by production canaries.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Any

from fabric_nats import NATSFabric
from memory_fabric import (
    MemoryFabric,
    MemoryType,
    OllamaEmbedder,
    QdrantMemoryClient,
    QueryRequest,
)


LOGGER = logging.getLogger("cas_fabric.canonical_memory_node")


def result_to_dict(result) -> dict[str, Any]:
    return {
        "score": result.score,
        "point_id": result.memory_id,
        "memory_id": result.memory_id,
        "content": result.content,
        "memory_type": result.memory_type.value,
        "source": result.metadata.get("source_node", result.metadata.get("source", "")),
        "metadata": result.metadata,
    }


class CanonicalMemoryNode:
    def __init__(self) -> None:
        self.fabric = NATSFabric(os.getenv("CAS_NATS_URL", "nats://localhost:4222"))
        self.qdrant = QdrantMemoryClient(os.getenv("CAS_QDRANT_URL", "http://localhost:6333"))
        self.embedder = OllamaEmbedder(
            os.getenv("CAS_OLLAMA_URL", "http://localhost:11434"),
            os.getenv("CAS_EMBED_MODEL", "nomic-embed-text:latest"),
        )
        self.memory: MemoryFabric | None = None

    async def start(self) -> None:
        await self.fabric.connect()
        await self.qdrant.connect()
        await self.embedder.connect()
        self.memory = MemoryFabric(self.fabric, self.qdrant, "canonical-memory-node", self.embedder)

        test_vec = await self.embedder("test")
        for collection in self.memory.collections.values():
            await self.qdrant.ensure_collection(collection, len(test_vec))
        await self.memory.values_memory.initialize(len(test_vec))
        self.memory._running = True

        await self.fabric.subscribe_async("capability.memory.write", self.handle_write)
        await self.fabric.subscribe_async("capability.memory.query", self.handle_query)
        LOGGER.info(
            "Canonical memory node ready: vector_size=%s md5=e65cd4c0af0c851d4b64ab2ea79de3c6",
            len(test_vec),
        )

    async def handle_write(self, envelope: dict) -> None:
        respond = envelope.get("respond")
        payload = envelope.get("payload", {})
        try:
            if self.memory is None:
                raise RuntimeError("memory fabric not initialized")
            memory_type = MemoryType(payload.get("type", payload.get("memory_type", "semantic")))
            memory_id = await self.memory.write_memory(
                memory_type=memory_type,
                content=str(payload["content"]),
                source_node=payload.get("source_node", payload.get("source", "unknown")),
                urgency=bool(payload.get("urgency", False)),
                metadata=payload.get("metadata", {}),
            )
            result = {"ok": True, "point_id": memory_id, "memory_id": memory_id}
        except Exception as exc:
            LOGGER.exception("canonical memory.write failed")
            result = {"ok": False, "error": str(exc)}
        if respond:
            await respond(result)

    async def handle_query(self, envelope: dict) -> None:
        respond = envelope.get("respond")
        payload = envelope.get("payload", {})
        try:
            if self.memory is None:
                raise RuntimeError("memory fabric not initialized")
            query = str(payload["query"])
            embedding = payload.get("query_embedding") or await self.embedder(query)
            req = QueryRequest(
                query=query,
                query_embedding=embedding,
                memory_types=[
                    MemoryType(mt)
                    for mt in payload.get("memory_types", [payload.get("memory_type", "semantic")])
                ],
                limit=int(payload.get("limit", 10)),
                node_id=str(payload.get("node_id", "canonical-memory-client")),
                include_values_context=bool(payload.get("include_values_context", True)),
            )
            results = await self.memory.query_memory(req)
            result = {"ok": True, "query": query, "results": [result_to_dict(item) for item in results]}
        except Exception as exc:
            LOGGER.exception("canonical memory.query failed")
            result = {"ok": False, "error": str(exc), "results": []}
        if respond:
            await respond(result)

    async def close(self) -> None:
        if self.memory:
            await self.memory.shutdown()
        await self.fabric.close()
        await self.qdrant.close()
        await self.embedder.close()


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    node = CanonicalMemoryNode()
    await node.start()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()
    await node.close()


if __name__ == "__main__":
    asyncio.run(main())
