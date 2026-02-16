"""
AADAP — Vector Store
=====================
pgvector-backed Tier 2 operational store for memory entities.

Invariants enforced:
- INV-08: Retrieval similarity ≥ 0.85 (SYSTEM_CONSTITUTION.md)
- Deprecated entities excluded from all searches
- Staleness < 90 days (DATA_AND_STATE.md §Vector Retrieval Rules)
- Provenance required on every entity

Usage:
    from aadap.memory.vector_store import VectorStore, MemoryEntity

    store = VectorStore()
    entity_id = await store.store(entity)
    results = await store.search(query_embedding)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


# ── Constants (non-negotiable) ──────────────────────────────────────────

MIN_SIMILARITY: float = 0.85
"""INV-08: Minimum cosine similarity for retrieval.  Non-negotiable."""

MAX_STALENESS_DAYS: int = 90
"""DATA_AND_STATE.md: Maximum age for vector retrieval results."""


# ── Data Classes ────────────────────────────────────────────────────────

@dataclass
class MemoryEntity:
    """Storable memory entity with embedding and governance metadata."""

    content: str
    embedding: list[float]
    entity_type: str
    provenance: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    confidence: float = 1.0
    use_count: int = 0
    validation_pass_rate: float = 1.0
    is_deprecated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SearchResult:
    """Single search result with similarity score."""

    entity: MemoryEntity
    similarity: float


# ── Vector Store ────────────────────────────────────────────────────────

class VectorStore:
    """
    In-memory vector store implementing the pgvector interface contract.

    Production deployment uses PostgreSQL + pgvector extension.  This
    implementation provides the full contract for Phase 6 validation
    and unit testing without requiring a live database.

    All invariants are enforced architecturally, not by caller convention.
    """

    def __init__(self) -> None:
        self._entities: dict[str, MemoryEntity] = {}

    # ── Store ────────────────────────────────────────────────────────────

    async def store(self, entity: MemoryEntity) -> str:
        """
        Persist a memory entity.

        Raises:
            ValueError: If provenance is missing (DATA_AND_STATE.md §Vector Retrieval Rules).
        """
        if not entity.embedding:
            raise ValueError("Embedding vector must not be empty.")
        if not entity.provenance or not entity.provenance.strip():
            raise ValueError(
                "Provenance is required for every memory entity "
                "(DATA_AND_STATE.md §Vector Retrieval Rules)."
            )

        entity.updated_at = datetime.now(timezone.utc)
        self._entities[entity.id] = entity
        return entity.id

    # ── Search ───────────────────────────────────────────────────────────

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        min_similarity: float = MIN_SIMILARITY,
    ) -> list[SearchResult]:
        """
        Cosine similarity search with invariant enforcement.

        Guarantees:
        - Results have similarity ≥ ``MIN_SIMILARITY`` (INV-08, hardcoded floor)
        - Deprecated entities are never returned
        - Stale entities (> 90 days) are never returned
        """
        # Enforce INV-08 floor — callers cannot weaken the threshold
        effective_min = max(min_similarity, MIN_SIMILARITY)
        now = datetime.now(timezone.utc)
        staleness_cutoff = now - timedelta(days=MAX_STALENESS_DAYS)

        results: list[SearchResult] = []
        for entity in self._entities.values():
            # Gate 1: deprecated exclusion
            if entity.is_deprecated:
                continue
            # Gate 2: staleness filter
            if entity.created_at < staleness_cutoff:
                continue
            # Gate 3: similarity threshold (INV-08)
            sim = self._cosine_similarity(query_embedding, entity.embedding)
            if sim < effective_min:
                continue
            results.append(SearchResult(entity=entity, similarity=sim))

        # Sort by similarity descending
        results.sort(key=lambda r: r.similarity, reverse=True)
        return results[:limit]

    # ── Get ──────────────────────────────────────────────────────────────

    async def get(self, entity_id: str) -> MemoryEntity | None:
        """Retrieve entity by ID.  Returns None if not found."""
        return self._entities.get(entity_id)

    # ── Promote ─────────────────────────────────────────────────────────

    async def promote(self, entity_id: str) -> None:
        """
        Mark an entity as promoted / trusted.

        Promotion criteria (DATA_AND_STATE.md §Memory Governance):
        - ≥ 3 successful uses
        - ≥ 90% validation pass rate
        - No critical failures in 30 days

        Validation of criteria is the caller's responsibility; this method
        records the promotion.
        """
        entity = self._entities.get(entity_id)
        if entity is None:
            raise KeyError(f"Entity {entity_id} not found.")
        entity.metadata["promoted"] = True
        entity.metadata["promoted_at"] = datetime.now(timezone.utc).isoformat()
        entity.updated_at = datetime.now(timezone.utc)

    # ── Deprecate ───────────────────────────────────────────────────────

    async def deprecate(self, entity_id: str) -> None:
        """
        Mark an entity as deprecated.  It will no longer appear in search results.

        Deprecation criteria (DATA_AND_STATE.md §Memory Governance):
        - ≥ 2 validation failures
        - Outdated schema / API
        - Confidence < 0.6
        """
        entity = self._entities.get(entity_id)
        if entity is None:
            raise KeyError(f"Entity {entity_id} not found.")
        entity.is_deprecated = True
        entity.metadata["deprecated_at"] = datetime.now(timezone.utc).isoformat()
        entity.updated_at = datetime.now(timezone.utc)

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            raise ValueError(
                f"Vector dimension mismatch: {len(a)} vs {len(b)}"
            )
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
