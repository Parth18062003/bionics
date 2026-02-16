"""
AADAP — Vector Store Tests
=============================
Tests for INV-08 enforcement, deprecated exclusion, staleness filter,
provenance requirement, and store/get round-trip.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aadap.memory.vector_store import (
    MAX_STALENESS_DAYS,
    MIN_SIMILARITY,
    MemoryEntity,
    VectorStore,
)


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_entity(
    content: str = "test content",
    embedding: list[float] | None = None,
    provenance: str = "test-system",
    is_deprecated: bool = False,
    created_at: datetime | None = None,
    **kwargs,
) -> MemoryEntity:
    """Create a test MemoryEntity with sensible defaults."""
    return MemoryEntity(
        content=content,
        embedding=embedding if embedding is not None else [1.0, 0.0, 0.0],
        entity_type="test",
        provenance=provenance,
        is_deprecated=is_deprecated,
        created_at=created_at or datetime.now(timezone.utc),
        **kwargs,
    )


# ── Store / Get Round-Trip ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_and_get():
    """store() persists entities that can be retrieved via get()."""
    store = VectorStore()
    entity = _make_entity()
    entity_id = await store.store(entity)
    retrieved = await store.get(entity_id)
    assert retrieved is not None
    assert retrieved.content == "test content"
    assert retrieved.provenance == "test-system"


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none():
    """get() returns None for unknown IDs."""
    store = VectorStore()
    assert await store.get("nonexistent") is None


# ── Provenance Enforcement ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_rejects_missing_provenance():
    """store() raises ValueError when provenance is empty."""
    store = VectorStore()
    entity = _make_entity(provenance="")
    with pytest.raises(ValueError, match="Provenance"):
        await store.store(entity)


@pytest.mark.asyncio
async def test_store_rejects_whitespace_provenance():
    """store() raises ValueError when provenance is whitespace-only."""
    store = VectorStore()
    entity = _make_entity(provenance="   ")
    with pytest.raises(ValueError, match="Provenance"):
        await store.store(entity)


# ── Empty Embedding ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_rejects_empty_embedding():
    """store() raises ValueError when embedding is empty."""
    store = VectorStore()
    entity = _make_entity(embedding=[])
    with pytest.raises(ValueError, match="Embedding"):
        await store.store(entity)


# ── INV-08: Similarity Threshold ────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_rejects_below_similarity_threshold():
    """INV-08: results with similarity < 0.85 must not be returned."""
    store = VectorStore()
    # Store entity with a specific direction
    entity = _make_entity(embedding=[1.0, 0.0, 0.0])
    await store.store(entity)

    # Search with orthogonal vector — cosine similarity = 0
    results = await store.search([0.0, 1.0, 0.0])
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_returns_high_similarity():
    """Search returns results when similarity ≥ 0.85 (INV-08)."""
    store = VectorStore()
    entity = _make_entity(embedding=[1.0, 0.0, 0.0])
    await store.store(entity)

    # Self-similarity = 1.0
    results = await store.search([1.0, 0.0, 0.0])
    assert len(results) == 1
    assert results[0].similarity >= MIN_SIMILARITY


@pytest.mark.asyncio
async def test_search_caller_cannot_weaken_threshold():
    """Even if caller passes min_similarity < 0.85, INV-08 floor holds."""
    store = VectorStore()
    entity = _make_entity(embedding=[1.0, 0.0, 0.0])
    await store.store(entity)

    # Orthogonal vector — sim = 0 — should NOT be returned regardless of caller threshold
    results = await store.search([0.0, 1.0, 0.0], min_similarity=0.0)
    assert len(results) == 0


# ── Deprecated Exclusion ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_excludes_deprecated():
    """Deprecated entities must not appear in search results."""
    store = VectorStore()
    entity = _make_entity(embedding=[1.0, 0.0, 0.0])
    await store.store(entity)
    await store.deprecate(entity.id)

    results = await store.search([1.0, 0.0, 0.0])
    assert len(results) == 0


@pytest.mark.asyncio
async def test_deprecate_sets_flag():
    """deprecate() sets is_deprecated on the entity."""
    store = VectorStore()
    entity = _make_entity()
    await store.store(entity)
    await store.deprecate(entity.id)

    retrieved = await store.get(entity.id)
    assert retrieved is not None
    assert retrieved.is_deprecated is True


@pytest.mark.asyncio
async def test_deprecate_nonexistent_raises():
    """deprecate() raises KeyError for unknown entity."""
    store = VectorStore()
    with pytest.raises(KeyError):
        await store.deprecate("nonexistent")


# ── Staleness Filter ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_excludes_stale():
    """Entities older than 90 days are excluded from search."""
    store = VectorStore()
    old_date = datetime.now(timezone.utc) - timedelta(days=MAX_STALENESS_DAYS + 1)
    entity = _make_entity(embedding=[1.0, 0.0, 0.0], created_at=old_date)
    await store.store(entity)

    results = await store.search([1.0, 0.0, 0.0])
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_includes_fresh():
    """Entities within 90 days are included in search results."""
    store = VectorStore()
    recent = datetime.now(timezone.utc) - timedelta(days=MAX_STALENESS_DAYS - 1)
    entity = _make_entity(embedding=[1.0, 0.0, 0.0], created_at=recent)
    await store.store(entity)

    results = await store.search([1.0, 0.0, 0.0])
    assert len(results) == 1


# ── Promote ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_promote_sets_metadata():
    """promote() records promotion in entity metadata."""
    store = VectorStore()
    entity = _make_entity()
    await store.store(entity)
    await store.promote(entity.id)

    retrieved = await store.get(entity.id)
    assert retrieved is not None
    assert retrieved.metadata.get("promoted") is True


@pytest.mark.asyncio
async def test_promote_nonexistent_raises():
    """promote() raises KeyError for unknown entity."""
    store = VectorStore()
    with pytest.raises(KeyError):
        await store.promote("nonexistent")


# ── Search Limit ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_respects_limit():
    """search() returns at most 'limit' results."""
    store = VectorStore()
    for i in range(5):
        entity = _make_entity(
            content=f"entity {i}",
            embedding=[1.0, 0.0, 0.0],
        )
        await store.store(entity)

    results = await store.search([1.0, 0.0, 0.0], limit=3)
    assert len(results) == 3


# ── MIN_SIMILARITY constant ────────────────────────────────────────────

def test_min_similarity_constant():
    """MIN_SIMILARITY is exactly 0.85 as per INV-08."""
    assert MIN_SIMILARITY == 0.85


def test_max_staleness_constant():
    """MAX_STALENESS_DAYS is 90 as per DATA_AND_STATE.md."""
    assert MAX_STALENESS_DAYS == 90
