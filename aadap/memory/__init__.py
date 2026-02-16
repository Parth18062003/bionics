"""
AADAP — Memory Integration Package
====================================
Multi-tier memory system with governance and retrieval validation.

Tiers (DATA_AND_STATE.md):
- Tier 1: Working Memory (Redis, TTL-based)
- Tier 2: Operational Store (PostgreSQL + pgvector)
- Tier 3: Archive (Blob Storage, 7-year retention)
- Tier 4: Knowledge Graph (PostgreSQL graph tables)

Phase 6 modules.
"""

from aadap.memory.archival import ArchivalPipeline, ArchivalRecord
from aadap.memory.embeddings import EmbeddingProvider, EmbeddingService
from aadap.memory.knowledge_graph import KnowledgeEdge, KnowledgeGraph, KnowledgeNode
from aadap.memory.retrieval_validator import RetrievalValidator, ValidatedResult
from aadap.memory.vector_store import MemoryEntity, SearchResult, VectorStore
from aadap.memory.working_memory import WorkingMemory

__all__ = [
    "ArchivalPipeline",
    "ArchivalRecord",
    "EmbeddingProvider",
    "EmbeddingService",
    "KnowledgeEdge",
    "KnowledgeGraph",
    "KnowledgeNode",
    "MemoryEntity",
    "RetrievalValidator",
    "SearchResult",
    "ValidatedResult",
    "VectorStore",
    "WorkingMemory",
]
