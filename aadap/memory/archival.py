"""
AADAP — Archival Pipeline
============================
Tier 3 archival pipeline for long-term memory retention.

Archives memory entities for 7-year retention (DATA_AND_STATE.md §Memory Tiers).
Archived entities are marked as deprecated in the vector store to prevent
retrieval via the normal search path.

Usage:
    from aadap.memory.archival import ArchivalPipeline

    pipeline = ArchivalPipeline(vector_store=store)
    record = await pipeline.archive(entity, storage_uri="blob://...")
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aadap.memory.vector_store import MemoryEntity, VectorStore


# ── Constants ───────────────────────────────────────────────────────────

DEFAULT_RETENTION_DAYS: int = 2555  # ~7 years (DATA_AND_STATE.md)


# ── Data Classes ────────────────────────────────────────────────────────

@dataclass
class ArchivalRecord:
    """Record of an archived memory entity."""

    original_entity_id: str
    storage_uri: str
    entity_type: str
    content_summary: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    retention_days: int = DEFAULT_RETENTION_DAYS
    metadata: dict[str, Any] = field(default_factory=dict)
    archived_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── Archival Pipeline ──────────────────────────────────────────────────

class ArchivalPipeline:
    """
    Manages the lifecycle of memory archival.

    When an entity is archived:
    1. An ``ArchivalRecord`` is created with retention metadata.
    2. The original entity is deprecated in the vector store (no longer searchable).
    3. The archive record is stored for Tier 3 retrieval.

    Production deployment: Blob Storage (Azure).  Phase 6 uses in-memory storage.
    """

    def __init__(self, vector_store: VectorStore) -> None:
        self._vector_store = vector_store
        self._records: dict[str, ArchivalRecord] = {}

    # ── Archive ─────────────────────────────────────────────────────────

    async def archive(
        self,
        entity: MemoryEntity,
        storage_uri: str,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ) -> ArchivalRecord:
        """
        Archive a memory entity.

        Steps:
        1. Create an archival record.
        2. Deprecate the entity in the vector store.
        3. Store the archival record.

        Args:
            entity: The memory entity to archive.
            storage_uri: URI where the entity content is stored (blob storage).
            retention_days: How long to retain (default ~7 years).

        Returns:
            The archival record.

        Raises:
            ValueError: If storage_uri is empty.
        """
        if not storage_uri or not storage_uri.strip():
            raise ValueError("storage_uri must not be empty.")

        record = ArchivalRecord(
            original_entity_id=entity.id,
            storage_uri=storage_uri,
            entity_type=entity.entity_type,
            content_summary=entity.content[:200] if entity.content else "",
            retention_days=retention_days,
            metadata={
                "original_provenance": entity.provenance,
                "original_confidence": entity.confidence,
                "original_use_count": entity.use_count,
            },
        )

        # Deprecate in vector store — prevents future retrieval
        try:
            await self._vector_store.deprecate(entity.id)
        except KeyError:
            # Entity may already be deprecated or removed — still archive
            pass

        self._records[record.id] = record
        return record

    # ── Retrieve ────────────────────────────────────────────────────────

    async def retrieve(self, archive_id: str) -> ArchivalRecord | None:
        """Retrieve an archival record by ID."""
        return self._records.get(archive_id)

    # ── List ────────────────────────────────────────────────────────────

    async def list_archived(
        self,
        entity_type: str | None = None,
    ) -> list[ArchivalRecord]:
        """
        List archived records, optionally filtered by entity type.

        Returns:
            List of archival records sorted by archived_at descending.
        """
        records = list(self._records.values())
        if entity_type is not None:
            records = [r for r in records if r.entity_type == entity_type]
        records.sort(key=lambda r: r.archived_at, reverse=True)
        return records
