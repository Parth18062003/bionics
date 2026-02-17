# PHASE 7.4 — END-TO-END INTEGRATION & OBSERVABILITY

## Objective
Validate the complete system end-to-end with observability
and governance guarantees.

## Modules in Scope
- Correlation ID propagation
- Distributed tracing
- End-to-end tests
- Approval enforcement validation

## Modules
- core/tracing.py
- frontend/tracing/
- tests/e2e/
- tests/integration/

## Authoritative Inputs
- SYSTEM_CONSTITUTION.md
- ARCHITECTURE.md
- PHASE_7_CONTRACTS.md

## Invariants
- Correlation ID must propagate UI → API → Orchestrator → Agent
- Approval gates must not be bypassed
- Audit trail must be complete

## Explicitly Forbidden
- Feature additions
- UI polish
- Refactors
- Performance tuning

## Required Tests
- Full pipeline test (NL input → sandbox deploy)
- Approval enforcement test
- Trace completeness test

## Definition of Done
- End-to-end pipeline passes
- Traces visible across all layers
- Audit logs complete
- No invariant violations
