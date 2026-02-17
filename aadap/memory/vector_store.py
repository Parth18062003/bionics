"""
AADAP — Vector Store
=====================
ChromaDB-backed Tier 2 operational store for memory entities.

Invariants enforced:
- INV-08: Retrieval similarity >= 0.85 (SYSTEM_CONSTITUTION.md)
- Deprecated entities excluded from all searches
- Staleness < 90 days (DATA_AND_STATE.md Section:Vector Retrieval Rules)
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

import chromadb
from chromadb.config import Settings as ChromaSettings


MIN_SIMILARITY: float = 0.85
"""INV-08: Minimum cosine similarity for retrieval.  Non-negotiable."""

MAX_STALENESS_DAYS: int = 90
"""DATA_AND_STATE.md: Maximum age for vector retrieval results."""

COLLECTION_NAME: str = "aadap_memory_entities"
"""Default ChromaDB collection name."""


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


class VectorStore:
    """
    ChromaDB-backed vector store implementing the vector store interface contract.

    Uses ChromaDB (free/local) with persistent storage. All invariants are
    enforced architecturally, not by caller convention.

    Configuration:
        persist_directory: Optional path for ChromaDB data persistence.
                          If None, uses in-memory ephemeral storage.
        collection_name: Name of the ChromaDB collection (default: aadap_memory_entities)
    """

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        if persist_directory:
            self._client = chromadb.PersistentClient(
                path=persist_directory,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        else:
            self._client = chromadb.EphemeralClient(
                settings=ChromaSettings(anonymized_telemetry=False),
            )

        self._collection_name = collection_name or f"{COLLECTION_NAME}_{uuid.uuid4().hex}"
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._entities_cache: dict[str, MemoryEntity] = {}

    def _entity_to_metadata(self, entity: MemoryEntity) -> dict[str, Any]:
        """Convert MemoryEntity to ChromaDB-compatible metadata dict."""
        return {
            "content": entity.content,
            "entity_type": entity.entity_type,
            "provenance": entity.provenance,
            "confidence": entity.confidence,
            "use_count": entity.use_count,
            "validation_pass_rate": entity.validation_pass_rate,
            "is_deprecated": entity.is_deprecated,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
            "metadata_json": str(entity.metadata),
        }

    def _metadata_to_entity(
        self, entity_id: str, embedding: list[float], metadata: dict[str, Any]
    ) -> MemoryEntity:
        """Convert ChromaDB metadata back to MemoryEntity."""
        import ast

        return MemoryEntity(
            id=entity_id,
            content=metadata.get("content", ""),
            embedding=embedding,
            entity_type=metadata.get("entity_type", ""),
            provenance=metadata.get("provenance", ""),
            confidence=float(metadata.get("confidence", 1.0)),
            use_count=int(metadata.get("use_count", 0)),
            validation_pass_rate=float(metadata.get("validation_pass_rate", 1.0)),
            is_deprecated=bool(metadata.get("is_deprecated", False)),
            metadata=ast.literal_eval(metadata.get("metadata_json", "{}")),
            created_at=datetime.fromisoformat(metadata["created_at"])
            if "created_at" in metadata
            else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(metadata["updated_at"])
            if "updated_at" in metadata
            else datetime.now(timezone.utc),
        )

    async def store(self, entity: MemoryEntity) -> str:
        """
        Persist a memory entity.

        Raises:
            ValueError: If provenance is missing (DATA_AND_STATE.md Section:Vector Retrieval Rules).
        """
        if not entity.embedding:
            raise ValueError("Embedding vector must not be empty.")
        if not entity.provenance or not entity.provenance.strip():
            raise ValueError(
                "Provenance is required for every memory entity "
                "(DATA_AND_STATE.md Section:Vector Retrieval Rules)."
            )

        entity.updated_at = datetime.now(timezone.utc)
        metadata = self._entity_to_metadata(entity)

        self._collection.upsert(
            ids=[entity.id],
            embeddings=[entity.embedding],
            metadatas=[metadata],
            documents=[entity.content],
        )
        self._entities_cache[entity.id] = entity
        return entity.id

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        min_similarity: float = MIN_SIMILARITY,
    ) -> list[SearchResult]:
        """
        Cosine similarity search with invariant enforcement.

        Guarantees:
        - Results have similarity >= MIN_SIMILARITY (INV-08, hardcoded floor)
        - Deprecated entities are never returned
        - Stale entities (> 90 days) are never returned
        """
        effective_min = max(min_similarity, MIN_SIMILARITY)
        now = datetime.now(timezone.utc)
        staleness_cutoff = now - timedelta(days=MAX_STALENESS_DAYS)

        fetch_limit = max(limit * 10, 100)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_limit,
            include=["embeddings", "metadatas", "distances"],
        )

        search_results: list[SearchResult] = []

        if not results["ids"] or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        embeddings_data = results.get("embeddings")
        embeddings = embeddings_data[0] if embeddings_data else []
        metadatas_data = results.get("metadatas")
        metadatas = metadatas_data[0] if metadatas_data else []
        distances_data = results.get("distances")
        distances = distances_data[0] if distances_data else []

        for i, entity_id in enumerate(ids):
            metadata = metadatas[i] if i < len(metadatas) else {}
            distance = distances[i] if i < len(distances) else 1.0
            embedding = embeddings[i] if i < len(embeddings) else []

            if metadata.get("is_deprecated", False):
                continue

            created_at_str = metadata.get("created_at", "")
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    if created_at < staleness_cutoff:
                        continue
                except (ValueError, TypeError):
                    pass

            similarity = 1.0 - distance
            if similarity < effective_min:
                continue

            entity = self._metadata_to_entity(
                entity_id,
                list(embedding) if embedding is not None and len(embedding) > 0 else [],
                metadata,
            )
            search_results.append(SearchResult(entity=entity, similarity=similarity))

        search_results.sort(key=lambda r: r.similarity, reverse=True)
        return search_results[:limit]

    async def get(self, entity_id: str) -> MemoryEntity | None:
        """Retrieve entity by ID.  Returns None if not found."""
        if entity_id in self._entities_cache:
            return self._entities_cache[entity_id]

        try:
            results = self._collection.get(
                ids=[entity_id],
                include=["embeddings", "metadatas"],
            )
            if not results["ids"]:
                return None

            metadata = results["metadatas"][0] if results["metadatas"] else {}
            emb_data = results.get("embeddings")
            embedding = emb_data[0] if emb_data else []
            entity = self._metadata_to_entity(
                entity_id,
                list(embedding) if embedding is not None and len(embedding) > 0 else [],
                metadata,
            )
            self._entities_cache[entity_id] = entity
            return entity
        except Exception:
            return None

    async def promote(self, entity_id: str) -> None:
        """
        Mark an entity as promoted / trusted.

        Promotion criteria (DATA_AND_STATE.md Section:Memory Governance):
        - >= 3 successful uses
        - >= 90% validation pass rate
        - No critical failures in 30 days

        Validation of criteria is the caller's responsibility; this method
        records the promotion.
        """
        entity = await self.get(entity_id)
        if entity is None:
            raise KeyError(f"Entity {entity_id} not found.")
        entity.metadata["promoted"] = True
        entity.metadata["promoted_at"] = datetime.now(timezone.utc).isoformat()
        entity.updated_at = datetime.now(timezone.utc)
        await self.store(entity)

    async def deprecate(self, entity_id: str) -> None:
        """
        Mark an entity as deprecated.  It will no longer appear in search results.

        Deprecation criteria (DATA_AND_STATE.md Section:Memory Governance):
        - >= 2 validation failures
        - Outdated schema / API
        - Confidence < 0.6
        """
        entity = await self.get(entity_id)
        if entity is None:
            raise KeyError(f"Entity {entity_id} not found.")
        entity.is_deprecated = True
        entity.metadata["deprecated_at"] = datetime.now(timezone.utc).isoformat()
        entity.updated_at = datetime.now(timezone.utc)
        await self.store(entity)

    async def delete(self, entity_id: str) -> None:
        """Permanently delete an entity from the store."""
        try:
            self._collection.delete(ids=[entity_id])
            self._entities_cache.pop(entity_id, None)
        except Exception:
            pass

    async def clear(self) -> None:
        """Clear all entities from the collection."""
        self._client.delete_collection(self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._entities_cache.clear()
