# PHASE 5 — SAFETY & APPROVAL SYSTEM CONTRACTS

## Objective
Implement the full multi-layer defense and approval workflow.

## Modules in Scope
- Static analysis gate (AST)
- Pattern matching gate
- Semantic risk scoring gate
- Approval Engine state machine
- Approval routing & escalation
- Notification service

## Modules
- safety/static_analysis.py
- safety/pattern_matcher.py
- safety/semantic_analysis.py
- safety/approval_engine.py
- safety/routing.py
- services/notifications.py

## Invariants
- No destructive op executes without approval
- No safety gate bypass
- Sandbox auto-approval is policy, not bypass

## Interfaces
- `evaluate(code) -> risk_result`
- `request_approval(operation)`
- `approve/reject()`

## Required Tests
- Destructive op detection
- Approval enforcement
- Timeout escalation

## Definition of Done
- DROP TABLE blocked
- Production write requires approval
- Rejection halts execution
