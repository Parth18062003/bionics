# DATA & STATE ARCHITECTURE — AADAP

## State Management
- Event-sourced
- Immutable events
- Checkpoints after every transition
- Replayable task state

## Core Entities
Task  
StateTransition  
Artifact  
ApprovalRequest  
Execution  
AuditEvent  

## Memory Tiers

Tier 1 — Working Memory (Redis, TTL-based)  
Tier 2 — Operational Store (PostgreSQL + pgvector)  
Tier 3 — Archive (Blob Storage, 7-year retention)  
Tier 4 — Knowledge Graph (PostgreSQL graph tables)

## Vector Retrieval Rules
- Cosine similarity ≥ 0.85
- Staleness < 90 days
- Provenance required
- Conflict resolution: recency > confidence > frequency

## Memory Governance
Promotion:
- ≥ 3 successful uses
- ≥ 90% validation pass
- No critical failures in 30 days

Deprecation:
- ≥ 2 validation failures
- Outdated schema/API
- Confidence < 0.6

Deprecated artifacts must not be retrieved.
