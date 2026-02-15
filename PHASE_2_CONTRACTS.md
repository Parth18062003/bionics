# PHASE 2 — ORCHESTRATION ENGINE CONTRACTS

## Objective
Implement the deterministic task lifecycle and orchestration backbone using LangGraph.

## Modules in Scope
- Task State Machine (25 states)
- LangGraph StateGraph definition
- Event sourcing (state transitions)
- Checkpoint persistence
- Task scheduler (priority-based)
- Loop detection & guards

## Modules (Authoritative)
- orchestrator/state_machine.py
- orchestrator/graph.py
- orchestrator/events.py
- orchestrator/checkpoints.py
- orchestrator/scheduler.py
- orchestrator/guards.py

## Invariants to Enforce
- Only AUTHORITATIVE states may exist
- All transitions must be persisted before acknowledgement
- Undefined transitions are P0 bugs
- Same state may not be entered >3 times

## Interfaces
- `create_task(input) -> task_id`
- `transition(task_id, next_state)`
- `replay(task_id) -> state`
- `schedule(task_id, priority)`

## Non-Goals
- No agent logic
- No safety gates
- No UI integration

## Required Tests
- State transition validity
- Replay correctness
- Loop detection
- Checkpoint recovery

## Definition of Done
- All 25 states implemented
- Illegal transitions blocked
- State replay works after simulated crash
