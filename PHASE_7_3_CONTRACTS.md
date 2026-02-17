# PHASE 7.3 — UI ↔ API WIRING

## Objective
Connect frontend UI to backend APIs and orchestrator behavior.

## Modules in Scope
- API client layer
- Data loaders
- Mutations and submissions
- Real-time updates (SSE/WebSocket)
- Error handling

## Modules
- frontend/api/
- frontend/hooks/
- frontend/loaders/
- frontend/mutations/

## Authoritative Inputs
- Backend API contracts
- UI_INTERACTION_FLOWS.md
- ARCHITECTURE.md (API & orchestration)

## Invariants
- UI must not bypass API
- API must not bypass orchestrator
- UX flows must match interaction definitions

## Explicitly Forbidden
- Changing UX flows
- Altering API semantics
- Adding frontend-only shortcuts

## Required Tests
- Task submission flow
- Approval submission flow
- Error propagation
- Real-time update verification

## Definition of Done
- UI actions trigger correct backend behavior
- Task states update in real time
- Errors surface with correct messaging
- No invariant violations
