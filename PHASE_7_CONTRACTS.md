# PHASE 7 — END-TO-END INTEGRATION & UI CONTRACTS

## Objective
Integrate all subsystems and expose functionality via UI and API.

## Modules in Scope
- Tanstack Start frontend
- REST API endpoints
- Orchestrator ↔ Agent ↔ Memory wiring
- Databricks execution integration
- Distributed tracing

## Modules
- frontend/
- api/routes/
- integrations/databricks_client.py
- core/tracing.py

## Invariants
- UI cannot bypass API
- API cannot bypass orchestrator
- Correlation ID propagated end-to-end

## Required Features
- Task submission
- Task status dashboard
- Approval UI
- Artifact viewer
- Real-time updates

## Required Tests
- Full pipeline integration test
- UI approval enforcement
- Correlation ID tracing

## Definition of Done
- NL requirement → validated sandbox deployment
- UI reflects real-time task state
