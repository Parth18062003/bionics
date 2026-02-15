# PHASE 6 — MEMORY INTEGRATION CONTRACTS

## Objective
Implement multi-tier memory with governance and retrieval validation.

## Modules in Scope
- Embedding service
- Vector store (pgvector)
- Retrieval validation
- Working memory (Redis)
- Knowledge graph
- Archival pipeline

## Modules
- memory/embeddings.py
- memory/vector_store.py
- memory/retrieval_validator.py
- memory/working_memory.py
- memory/knowledge_graph.py
- memory/archival.py

## Invariants
- Retrieval similarity ≥ 0.85
- Deprecated memory must not be returned
- Working memory is TTL-bound

## Interfaces
- `store(entity)`
- `search(query) -> results`
- `promote/deprecate(entity)`

## Required Tests
- Similarity threshold enforcement
- Deprecation exclusion
- Archival correctness

## Definition of Done
- Agents can store & retrieve context
- Low-confidence results filtered
