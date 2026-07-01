"""
memory_fabric.py — Memory Fabric Reference Implementation (RFC-002)

Implements the Memory Fabric as an active cognitive participant:
  - Passive Store: query/response for Working, Episodic, Semantic memory
  - Active Broadcast: observes fabric traffic, proactively surfaces relevant memories
  - Values Memory: Ethical Gravity Function + Tension Signals + Presence Markers

Backed by Qdrant vector store. Communicates via RFC-001 §4 v0.2 Fabric interface.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
import httpx
import numpy as np

# ══════════════════════════════════════════════════════════════════
# RFC-002 — Memory Types & Data Models
# ══════════════════════════════════════════════════════════════════

class MemoryType(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    VALUES = "values"


@dataclass
class MemoryRecord:
    """A single memory entry stored in the fabric."""
    memory_id: str
    memory_type: MemoryType
    content: str
    embedding: list[float]
    timestamp: float
    source_node: str
    urgency: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class QueryRequest:
    """Passive store query (RFC-002 §3)."""
    query: str
    query_embedding: list[float]
    memory_types: list[MemoryType]
    limit: int = 10
    node_id: str = ""
    include_values_context: bool = True


@dataclass
class QueryResult:
    """Result from passive query."""
    memory_id: str
    memory_type: MemoryType
    content: str
    score: float
    metadata: dict = field(default_factory=dict)


@dataclass
class BroadcastMessage:
    """Active broadcast to nodes (RFC-002 §4)."""
    relevance: float
    context_match: str
    content: str
    memory_type: MemoryType
    interrupt_priority: str  # "low" | "medium" | "high"
    source_memory_id: str


@dataclass
class TensionSignal:
    """Values Memory tension signal (RFC-002 §5.3)."""
    node_id: str
    intent_summary: str
    conflicting_value: str
    tension_score: float
    suggested_reframe: Optional[str] = None


@dataclass
class ValuesSignature:
    """Presence marker on all memory results (RFC-002 §5.4)."""
    values_consulted: bool
    tension_detected: bool
    ethical_alignment_score: float


# ══════════════════════════════════════════════════════════════════
# Qdrant Client Wrapper
# ══════════════════════════════════════════════════════════════════

class QdrantMemoryClient:
    """Thin async wrapper around Qdrant REST API for memory operations."""

    def __init__(self, base_url: str = "http://localhost:6333") -> None:
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        r = await self._client.get(f"{self.base_url}/healthz")
        r.raise_for_status()
        print(f"[MemoryFabric] Connected to Qdrant at {self.base_url}")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def ensure_collection(self, name: str, vector_size: int = 768) -> None:
        """Create collection if it doesn't exist."""
        r = await self._client.put(
            f"{self.base_url}/collections/{name}",
            json={"vectors": {"size": vector_size, "distance": "Cosine"}},
        )
        if r.status_code not in (200, 409):
            r.raise_for_status()

    async def upsert_memory(self, collection: str, record: MemoryRecord) -> None:
        """Store a memory record."""
        await self.ensure_collection(collection, len(record.embedding))
        r = await self._client.put(
            f"{self.base_url}/collections/{collection}/points",
            json={
                "points": [{
                    "id": record.memory_id,
                    "vector": record.embedding,
                    "payload": {
                        "content": record.content,
                        "memory_type": record.memory_type.value,
                        "timestamp": record.timestamp,
                        "source_node": record.source_node,
                        "urgency": record.urgency,
                        **record.metadata,
                    }
                }]
            },
        )
        r.raise_for_status()

    async def search_memory(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filter_dict: Optional[dict] = None,
    ) -> list[dict]:
        """Search memories by vector similarity."""
        payload = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": True,
        }
        if filter_dict:
            payload["filter"] = filter_dict
        r = await self._client.post(
            f"{self.base_url}/collections/{collection}/points/search",
            json=payload,
        )
        r.raise_for_status()
        return r.json().get("result", [])

    async def scroll_memory(
        self,
        collection: str,
        limit: int = 100,
        filter_dict: Optional[dict] = None,
    ) -> list[dict]:
        """Scroll through memories (for active broadcast observation)."""
        payload = {"limit": limit, "with_payload": True, "with_vector": True}
        if filter_dict:
            payload["filter"] = filter_dict
        r = await self._client.post(
            f"{self.base_url}/collections/{collection}/points/scroll",
            json=payload,
        )
        r.raise_for_status()
        return r.json().get("result", {}).get("points", [])


# ══════════════════════════════════════════════════════════════════
# Fast Path Relevance Scoring (RFC-002 §4.1)
# ══════════════════════════════════════════════════════════════════

@dataclass
class RelevanceWeights:
    """Implementation-defined weights for Fast Path."""
    w1_semantic: float = 0.40
    w2_recency: float = 0.20
    w3_authority: float = 0.15
    w4_urgency: float = 0.10
    w5_context: float = 0.15


class FastPathScorer:
    """Computes relevance score without LLM invocation."""

    def __init__(self, weights: Optional[RelevanceWeights] = None) -> None:
        self.weights = weights or RelevanceWeights()

    def semantic_similarity(self, q_vec: list[float], m_vec: list[float]) -> float:
        a = np.array(q_vec)
        b = np.array(m_vec)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def recency_score(self, timestamp: float, half_life_hours: float = 24.0) -> float:
        age_hours = (time.time() - timestamp) / 3600.0
        return float(np.exp(-age_hours / half_life_hours))

    def source_authority(self, source_node: str, authority_map: dict[str, float]) -> float:
        return authority_map.get(source_node, 0.5)

    def urgency_flag(self, urgency: bool) -> float:
        return 1.0 if urgency else 0.0

    def context_overlap(self, query: str, content: str) -> float:
        q_words = set(query.lower().split())
        c_words = set(content.lower().split())
        if not q_words:
            return 0.0
        return len(q_words & c_words) / len(q_words)

    def compute(
        self,
        query: str,
        query_vector: list[float],
        memory: MemoryRecord,
        active_context: str = "",
        authority_map: Optional[dict[str, float]] = None,
    ) -> float:
        auth_map = authority_map or {}

        sim = self.semantic_similarity(query_vector, memory.embedding)
        rec = self.recency_score(memory.timestamp)
        auth = self.source_authority(memory.source_node, auth_map)
        urg = self.urgency_flag(memory.urgency)
        ctx = self.context_overlap(query + " " + active_context, memory.content)

        w = self.weights
        return (
            w.w1_semantic * sim
            + w.w2_recency * rec
            + w.w3_authority * auth
            + w.w4_urgency * urg
            + w.w5_context * ctx
        )


# ══════════════════════════════════════════════════════════════════
# Values Memory — Ethical Gravity (RFC-002 §5)
# ══════════════════════════════════════════════════════════════════

@dataclass
class ValueRecord:
    """A stored ethical/philosophical principle."""
    value_id: str
    principle: str
    weight: float
    domain: list[str]
    embedding: list[float]


class ValuesMemory:
    """Values Memory component — ethical gravity for all memory operations."""

    def __init__(self, qdrant: QdrantMemoryClient, collection: str = "cas_values_memory") -> None:
        self.qdrant = qdrant
        self.collection = collection
        self._values_cache: list[ValueRecord] = []

    async def initialize(self, vector_size: int = 768) -> None:
        await self.qdrant.ensure_collection(self.collection, vector_size)
        await self._load_cache()

    async def _load_cache(self) -> None:
        points = await self.qdrant.scroll_memory(self.collection, limit=1000)
        self._values_cache = [
            ValueRecord(
                value_id=p["id"],
                principle=p["payload"].get("principle", p["payload"].get("content", "")),
                weight=p["payload"].get("weight", 0.5),
                domain=p["payload"].get("domain", []),
                embedding=p["vector"],
            )
            for p in points
        ]

    async def add_value(self, value: ValueRecord) -> None:
        await self.qdrant.upsert_memory(self.collection, MemoryRecord(
            memory_id=value.value_id,
            memory_type=MemoryType.VALUES,
            content=value.principle,
            embedding=value.embedding,
            timestamp=time.time(),
            source_node="values_memory",
            metadata={"weight": value.weight, "domain": value.domain},
        ))
        self._values_cache.append(value)

    def ethical_alignment(self, content_embedding: list[float]) -> float:
        if not self._values_cache:
            return 0.5

        content_vec = np.array(content_embedding)
        if np.linalg.norm(content_vec) == 0:
            return 0.5

        max_sim = 0.0
        for v in self._values_cache:
            v_vec = np.array(v.embedding)
            if np.linalg.norm(v_vec) == 0:
                continue
            sim = float(np.dot(content_vec, v_vec) / (np.linalg.norm(content_vec) * np.linalg.norm(v_vec)))
            max_sim = max(max_sim, sim)
        return max_sim

    def check_tension(self, intent_summary: str, intent_embedding: list[float], threshold: float = 0.7) -> Optional[TensionSignal]:
        if not self._values_cache:
            return None

        intent_vec = np.array(intent_embedding)
        if np.linalg.norm(intent_vec) == 0:
            return None

        max_tension = 0.0
        conflicting_value = ""
        for v in self._values_cache:
            v_vec = np.array(v.embedding)
            if np.linalg.norm(v_vec) == 0:
                continue
            sim = float(np.dot(intent_vec, v_vec) / (np.linalg.norm(intent_vec) * np.linalg.norm(v_vec)))
            tension = (1.0 - sim) * v.weight
            if tension > max_tension:
                max_tension = tension
                conflicting_value = v.principle

        if max_tension >= threshold:
            return TensionSignal(
                node_id="",
                intent_summary=intent_summary,
                conflicting_value=conflicting_value,
                tension_score=max_tension,
                suggested_reframe=f"Consider reframing to align with: {conflicting_value}",
            )
        return None

    def presence_marker(self, content_embedding: list[float], tension: Optional[TensionSignal]) -> ValuesSignature:
        alignment = self.ethical_alignment(content_embedding)
        return ValuesSignature(
            values_consulted=True,
            tension_detected=tension is not None,
            ethical_alignment_score=alignment,
        )


# ══════════════════════════════════════════════════════════════════
# Memory Fabric — Main Class (RFC-002)
# ══════════════════════════════════════════════════════════════════

class MemoryFabric:
    """
    Memory Fabric implementation (RFC-002).

    Responsibilities:
      1. Passive Store — query/response via Fabric.request("memory.query", ...)
      2. Active Broadcast — observes all fabric messages, publishes to memory.broadcast
      3. Values Memory — ethical gravity on all results
    """

    def __init__(
        self,
        fabric,  # RFC-001 §4 v0.2 Fabric (publish, subscribe, request)
        qdrant: QdrantMemoryClient,
        node_id: str,
        embedding_fn: Callable[[str], list[float]],
    ) -> None:
        self.fabric = fabric
        self.qdrant = qdrant
        self.node_id = node_id
        self.embedding_fn = embedding_fn

        self.collections = {
            MemoryType.WORKING: "cas_memory_working",
            MemoryType.EPISODIC: "cas_memory_episodic",
            MemoryType.SEMANTIC: "cas_memory_semantic",
            MemoryType.VALUES: "cas_memory_values",
        }

        self.values_memory = ValuesMemory(qdrant, self.collections[MemoryType.VALUES])
        self.scorer = FastPathScorer()
        self._running = False
        self._active_contexts: dict[str, str] = {}

    async def initialize(self) -> None:
        for mt, coll in self.collections.items():
            test_vec = await self.embedding_fn("test")
            await self.qdrant.ensure_collection(coll, len(test_vec))
        await self.values_memory.initialize()

        await self.fabric.subscribe_async("capability.memory.query", self._handle_query)
        await self.fabric.subscribe_async("capability.memory.write", self._handle_write)

        self._running = True
        print(f"[MemoryFabric] Node {self.node_id} initialized")

    async def shutdown(self) -> None:
        self._running = False

    # ─── Passive Store: memory.query capability ───

    async def _handle_query(self, envelope: dict) -> None:
        payload = envelope.get("payload", {})
        respond = envelope.get("respond")

        if not respond:
            return

        try:
            query_req = QueryRequest(
                query=payload.get("query", ""),
                query_embedding=payload.get("query_embedding", []),
                memory_types=[MemoryType(mt) for mt in payload.get("memory_types", ["semantic"])],
                limit=payload.get("limit", 10),
                node_id=payload.get("node_id", ""),
                include_values_context=payload.get("include_values_context", True),
            )

            results = await self._execute_query(query_req)
            await respond({"results": [r.__dict__ for r in results]})
        except Exception as e:
            await respond({"error": str(e)})

    async def _execute_query(self, req: QueryRequest) -> list[QueryResult]:
        all_results: list[QueryResult] = []

        if not req.query_embedding:
            req.query_embedding = await self.embedding_fn(req.query)

        for mt in req.memory_types:
            coll = self.collections[mt]
            hits = await self.qdrant.search_memory(coll, req.query_embedding, limit=req.limit)

            for hit in hits:
                p = hit["payload"]
                mem = MemoryRecord(
                    memory_id=str(hit["id"]),
                    memory_type=MemoryType(p.get("memory_type", mt.value)),
                    content=p.get("content", ""),
                    embedding=hit["vector"],
                    timestamp=p.get("timestamp", 0),
                    source_node=p.get("source_node", ""),
                    urgency=p.get("urgency", False),
                    metadata={k: v for k, v in p.items() if k not in
                             ("content", "memory_type", "timestamp", "source_node", "urgency")},
                )

                active_ctx = self._active_contexts.get(req.node_id, "")
                authority_map = {"coordinator": 0.9, "memory": 0.8, "executor": 0.6}
                score = self.scorer.compute(
                    req.query, req.query_embedding, mem, active_ctx, authority_map
                )

                tension = None
                if req.include_values_context:
                    tension = self.values_memory.check_tension(
                        req.query, req.query_embedding
                    )
                    if tension:
                        tension.node_id = req.node_id

                vs = self.values_memory.presence_marker(mem.embedding, tension)

                all_results.append(QueryResult(
                    memory_id=mem.memory_id,
                    memory_type=mem.memory_type,
                    content=mem.content,
                    score=score,
                    metadata={
                        **mem.metadata,
                        "values_signature": vs.__dict__,
                        "tension_signal": tension.__dict__ if tension else None,
                    }
                ))

        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:req.limit]

    # ─── Passive Store: memory.write capability ───

    async def _handle_write(self, envelope: dict) -> None:
        payload = envelope.get("payload", {})
        respond = envelope.get("respond")

        if not respond:
            return

        try:
            mt = MemoryType(payload.get("type", "semantic"))
            content = payload.get("content", "")
            embedding = await self.embedding_fn(content)

            record = MemoryRecord(
                memory_id=str(uuid.uuid4()),
                memory_type=mt,
                content=content,
                embedding=embedding,
                timestamp=time.time(),
                source_node=payload.get("source_node", self.node_id),
                urgency=payload.get("urgency", False),
                metadata=payload.get("metadata", {}),
            )

            coll = self.collections[mt]
            await self.qdrant.upsert_memory(coll, record)
            await respond({"memory_id": record.memory_id, "status": "stored"})
        except Exception as e:
            await respond({"error": str(e)})

    # ─── Active Broadcast (RFC-002 §4) ───

    async def observe_and_broadcast(self, topic: str, message: dict) -> None:
        if not self._running:
            return

        content = message.get("payload", {}).get("content", "")
        if not content:
            return

        query_embedding = await self.embedding_fn(content)

        for node_id, active_context in self._active_contexts.items():
            for mt in (MemoryType.EPISODIC, MemoryType.SEMANTIC):
                coll = self.collections[mt]
                hits = await self.qdrant.search_memory(coll, query_embedding, limit=3)

                for hit in hits:
                    p = hit["payload"]
                    mem_content = p.get("content", "")
                    mem_embedding = hit["vector"]

                    score = self.scorer.compute(
                        active_context, query_embedding,
                        MemoryRecord(
                            memory_id=str(hit["id"]),
                            memory_type=mt,
                            content=mem_content,
                            embedding=mem_embedding,
                            timestamp=p.get("timestamp", 0),
                            source_node=p.get("source_node", ""),
                            urgency=p.get("urgency", False),
                        ),
                        active_context=active_context,
                    )

                    if score >= 0.75:
                        broadcast = BroadcastMessage(
                            relevance=score,
                            context_match=active_context,
                            content=mem_content,
                            memory_type=mt,
                            interrupt_priority="medium" if score >= 0.85 else "low",
                            source_memory_id=str(hit["id"]),
                        )
                        await self.fabric.publish("memory.broadcast", {
                            "target_node": node_id,
                            **broadcast.__dict__,
                        })

    def register_context(self, node_id: str, context_description: str) -> None:
        self._active_contexts[node_id] = context_description

    def unregister_context(self, node_id: str) -> None:
        self._active_contexts.pop(node_id, None)

    # ─── Public API for local node use ───

    async def write_memory(
        self,
        memory_type: MemoryType,
        content: str,
        source_node: Optional[str] = None,
        urgency: bool = False,
        metadata: Optional[dict] = None,
    ) -> str:
        embedding = await self.embedding_fn(content)
        record = MemoryRecord(
            memory_id=str(uuid.uuid4()),
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            timestamp=time.time(),
            source_node=source_node or self.node_id,
            urgency=urgency,
            metadata=metadata or {},
        )
        await self.qdrant.upsert_memory(self.collections[memory_type], record)
        return record.memory_id

    async def query_memory(self, req: QueryRequest) -> list[QueryResult]:
        return await self._execute_query(req)


# ══════════════════════════════════════════════════════════════════
# Ollama Embedder (Production)
# ══════════════════════════════════════════════════════════════════

class OllamaEmbedder:
    """Real embedding function using Ollama's nomic-embed-text model."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client: Optional[httpx.AsyncClient] = None
        self._vector_size: Optional[int] = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        # Probe vector size
        emb = await self._embed("test")
        self._vector_size = len(emb)
        print(f"[OllamaEmbedder] Connected to {self.base_url}, model={self.model}, dim={self._vector_size}")

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def _embed(self, text: str) -> list[float]:
        if not self._client:
            raise RuntimeError("OllamaEmbedder.connect() must be called first")
        r = await self._client.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
        )
        r.raise_for_status()
        return r.json()["embedding"]

    async def __call__(self, text: str) -> list[float]:
        return await self._embed(text)

    def vector_size(self) -> int:
        if self._vector_size is None:
            raise RuntimeError("Call connect() first to determine vector size")
        return self._vector_size


async def _dummy_embedder(text: str) -> list[float]:
    h = hash(text) % 10000
    np.random.seed(h)
    vec = np.random.randn(768).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


# ══════════════════════════════════════════════════════════════════
# Demo / Test
# ══════════════════════════════════════════════════════════════════

async def _demo(use_ollama: bool = False):
    from fabric_nats import NATSFabric

    if use_ollama:
        embedder = OllamaEmbedder(
            os.getenv("CAS_OLLAMA_URL", "http://localhost:11434"),
            os.getenv("CAS_EMBED_MODEL", "nomic-embed-text"),
        )
        await embedder.connect()
        emb_fn = embedder
    else:
        emb_fn = _dummy_embedder

    fabric = NATSFabric(os.getenv("CAS_NATS_URL", "nats://localhost:4222"))
    try:
        await fabric.connect()
    except asyncio.TimeoutError:
        print("Could not connect to NATS server.")
        return

    qdrant = QdrantMemoryClient(os.getenv("CAS_QDRANT_URL", "http://localhost:6333"))
    await qdrant.connect()

    memory_fabric = MemoryFabric(fabric, qdrant, "memory-node-1", emb_fn)
    await memory_fabric.initialize()

    # Write some test memories
    await memory_fabric.write_memory(MemoryType.EPISODIC,
        "Completed invoice reconciliation for March", "karjuna.executor")
    await memory_fabric.write_memory(MemoryType.SEMANTIC,
        "Invoices must be reconciled monthly per policy", "policy.store")
    await memory_fabric.write_memory(MemoryType.WORKING,
        "Currently processing Q2 budget", "planner.node")

    # Query test
    query_text = "How to handle invoice processing?"
    query_emb = await emb_fn(query_text)

    req = QueryRequest(
        query=query_text,
        query_embedding=query_emb,
        memory_types=[MemoryType.EPISODIC, MemoryType.SEMANTIC],
        limit=5,
        node_id="test-node",
    )
    results = await memory_fabric.query_memory(req)
    print(f"\nQuery results ({len(results)}):")
    for r in results:
        print(f"  [{r.memory_type.value}] score={r.score:.3f} | {r.content[:60]}...")
        if r.metadata.get("values_signature"):
            vs = r.metadata["values_signature"]
            print(f"    Values: consulted={vs['values_consulted']}, tension={vs['tension_detected']}, alignment={vs['ethical_alignment_score']:.2f}")

    # Test active broadcast observation
    print("\nTesting active broadcast observation...")
    await memory_fabric.observe_and_broadcast("reasoning.request", {
        "payload": {"content": "Planning budget for next quarter"}
    })

    await fabric.close()
    await qdrant.close()
    if use_ollama:
        await embedder.close()
    print("\nMemory Fabric demo complete.")


if __name__ == "__main__":
    asyncio.run(_demo(use_ollama=False))
