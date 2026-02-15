# SYSTEM CONSTITUTION — AADAP

## Core Purpose
AADAP is a governed, deterministic, multi-agent AI platform that autonomously executes data engineering tasks in real cloud environments while enforcing strict safety, auditability, and human-in-the-loop controls.

## Architectural Philosophy
- Determinism over convenience
- Safety by design (architectural, not policy-based)
- Explicit state over implicit behavior
- Modularity with strict boundaries
- Observability-first

## Non-Goals
- No free-form autonomous execution
- No agent-to-agent side effects outside orchestrator
- No self-modifying architecture
- No bypass of safety gates or approvals

## System Invariants (Non-Negotiable)
INV-01 No destructive operation executes without explicit human approval  
INV-02 All state transitions are persisted before acknowledgment  
INV-03 Agent self-correction loops are bounded (max 3 attempts)  
INV-04 Token budget per task is enforced (default 50,000 tokens)  
INV-05 Sandbox execution is isolated from production data  
INV-06 Complete audit trail for all actions and decisions  
INV-07 All generated code must pass validation before deployment  
INV-08 Memory retrieval requires similarity ≥ 0.85  
INV-09 Approval-required transitions must generate a DecisionExplanation artifact  

Violation of any invariant is a P0 system failure.

## Autonomy Policy Matrix (Authoritative)

| Environment | Operation | Approval Required |
|-----------|-----------|------------------|
| SANDBOX | Read-only | NO |
| SANDBOX | Write (non-destructive) | NO |
| SANDBOX | Destructive | YES |
| PRODUCTION | Read-only | NO |
| PRODUCTION | Write | YES |
| PRODUCTION | Destructive | YES |
| ANY | Schema change | YES |
| ANY | Permission change | YES |

## Change Control Rules
- Invariants may not be changed without explicit approval
- Architecture changes require documented Architecture Change Record
- Silent contract changes are forbidden

## Failure Handling Model
Fail fast → checkpoint → retry → alternate → escalate → terminate

## AI IDE Hard Stop Conditions
The AI must stop and escalate if:
- Invariants conflict
- Undefined state transitions exist
- Authoritative documents contradict
- Safety behavior is ambiguous
- External systems deviate from spec
