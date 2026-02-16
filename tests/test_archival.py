"""
AADAP — Archival Pipeline Tests
==================================
Tests for archival record creation, retrieval, deprecation of source entities,
and list filtering.
"""

from __future__ import annotations

import pytest

from aadap.memory.archival import ArchivalPipeline, ArchivalRecord, DEFAULT_RETENTION_DAYS
from aadap.memory.vector_store import MemoryEntity, VectorStore


# ── Helpers ─────────────────────────────────────────────────────────────

def _make_entity(content: str = "test content") -> MemoryEntity:
    return MemoryEntity(
        content=content,
        embedding=[1.0, 0.0, 0.0],
        entity_type="code_pattern",
        provenance="test-system",
    )


@pytest.fixture
def store():
    return VectorStore()


@pytest.fixture
def pipeline(store):
    return ArchivalPipeline(vector_store=store)


# ── Archive Creates Record ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archive_creates_record(pipeline, store):
    """archive() creates an ArchivalRecord with correct metadata."""
    entity = _make_entity()
    await store.store(entity)

    record = await pipeline.archive(entity, storage_uri="blob://archive/test.bin")
    assert record.original_entity_id == entity.id
    assert record.storage_uri == "blob://archive/test.bin"
    assert record.entity_type == "code_pattern"
    assert record.retention_days == DEFAULT_RETENTION_DAYS


@pytest.mark.asyncio
async def test_archive_default_retention():
    """Default retention is approximately 7 years (2555 days)."""
    assert DEFAULT_RETENTION_DAYS == 2555


# ── Archive Deprecates Source ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_archive_deprecates_entity(pipeline, store):
    """Archiving an entity marks it as deprecated in the vector store."""
    entity = _make_entity()
    await store.store(entity)

    await pipeline.archive(entity, storage_uri="blob://test")

    # Entity should now be deprecated
    retrieved = await store.get(entity.id)
    assert retrieved is not None
    assert retrieved.is_deprecated is True


@pytest.mark.asyncio
async def test_archive_deprecated_not_searchable(pipeline, store):
    """Archived (deprecated) entities don't appear in search results."""
    entity = _make_entity()
    await store.store(entity)
    await pipeline.archive(entity, storage_uri="blob://test")

    results = await store.search([1.0, 0.0, 0.0])
    assert len(results) == 0


# ── Retrieve ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retrieve_record(pipeline, store):
    """retrieve() returns the archived record by ID."""
    entity = _make_entity()
    await store.store(entity)
    record = await pipeline.archive(entity, storage_uri="blob://test")

    retrieved = await pipeline.retrieve(record.id)
    assert retrieved is not None
    assert retrieved.id == record.id


@pytest.mark.asyncio
async def test_retrieve_nonexistent_returns_none(pipeline):
    """retrieve() returns None for unknown archive IDs."""
    assert await pipeline.retrieve("nonexistent") is None


# ── List Archived ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_archived_all(pipeline, store):
    """list_archived returns all records when no filter."""
    for i in range(3):
        entity = _make_entity(f"content {i}")
        await store.store(entity)
        await pipeline.archive(entity, storage_uri=f"blob://test/{i}")

    records = await pipeline.list_archived()
    assert len(records) == 3


@pytest.mark.asyncio
async def test_list_archived_by_entity_type(pipeline, store):
    """list_archived filters by entity_type."""
    e1 = MemoryEntity(
        content="pattern 1", embedding=[1.0], entity_type="code_pattern",
        provenance="test",
    )
    e2 = MemoryEntity(
        content="schema 1", embedding=[1.0], entity_type="schema",
        provenance="test",
    )
    await store.store(e1)
    await store.store(e2)
    await pipeline.archive(e1, storage_uri="blob://1")
    await pipeline.archive(e2, storage_uri="blob://2")

    code_records = await pipeline.list_archived(entity_type="code_pattern")
    assert len(code_records) == 1
    assert code_records[0].entity_type == "code_pattern"


@pytest.mark.asyncio
async def test_list_archived_empty(pipeline):
    """list_archived returns empty list when nothing is archived."""
    assert await pipeline.list_archived() == []


# ── Validation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archive_empty_uri_raises(pipeline, store):
    """archive() raises ValueError on empty storage_uri."""
    entity = _make_entity()
    await store.store(entity)
    with pytest.raises(ValueError, match="storage_uri"):
        await pipeline.archive(entity, storage_uri="")


@pytest.mark.asyncio
async def test_archive_entity_not_in_store(pipeline, store):
    """archive() succeeds even if entity not in store (graceful deprecation)."""
    entity = _make_entity()
    # Don't store it in vector store
    record = await pipeline.archive(entity, storage_uri="blob://test")
    assert record is not None
    assert record.original_entity_id == entity.id


# ── Metadata Preservation ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archive_preserves_metadata(pipeline, store):
    """archive() captures original entity metadata in the archival record."""
    entity = _make_entity()
    entity.confidence = 0.92
    entity.use_count = 15
    await store.store(entity)

    record = await pipeline.archive(entity, storage_uri="blob://test")
    assert record.metadata["original_confidence"] == 0.92
    assert record.metadata["original_use_count"] == 15
    assert record.metadata["original_provenance"] == "test-system"
