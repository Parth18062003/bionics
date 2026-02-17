"""
AADAP — LangGraph StateGraph Definition
==========================================
Orchestration backbone graph using LangGraph.

Architecture layer: L5 (Orchestration).

Defines the structure of the 25-state task lifecycle as a LangGraph
StateGraph.  Nodes are passthrough stubs — actual agent logic is
Phase 3+.

Top-level API:
    create_task(...)   → task_id
    transition(...)    → new state
    replay(...)        → current state
    schedule(...)      → enqueue
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from aadap.core.logging import get_logger
from aadap.db.models import Task
from aadap.db.session import get_db_session
from aadap.orchestrator.checkpoints import CheckpointManager
from aadap.orchestrator.events import EventStore
from aadap.orchestrator.guards import Guards
from aadap.orchestrator.scheduler import TaskScheduler
from aadap.orchestrator.state_machine import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    TaskState,
    TaskStateMachine,
)

logger = get_logger("aadap.orchestrator.graph")


# ── Graph State Schema ──────────────────────────────────────────────────


class OrchestratorState(TypedDict, total=False):
    """State carried through the LangGraph execution."""

    task_id: str
    current_state: str
    previous_state: str | None
    triggered_by: str | None
    reason: str | None
    metadata: dict[str, Any]


# ── Node Functions ──────────────────────────────────────────────────────
# Stub nodes — each records its state name.  Agent logic deferred to Phase 3+.


def _make_node(state_name: str):
    """Factory producing a stub node for the given state."""

    def node_fn(state: OrchestratorState) -> OrchestratorState:
        return {
            **state,
            "previous_state": state.get("current_state"),
            "current_state": state_name,
        }

    node_fn.__name__ = f"node_{state_name.lower()}"
    node_fn.__doc__ = f"Stub node for {state_name} state."
    return node_fn


# ── Routing ─────────────────────────────────────────────────────────────


def _route_from(state_name: str):
    """
    Build a conditional router for outgoing edges of ``state_name``.

    The router reads ``current_state`` from the graph state and returns
    the matching node name.  If the state is terminal, it returns END.
    """
    allowed = VALID_TRANSITIONS.get(TaskState(state_name), frozenset())

    def router(state: OrchestratorState) -> str:
        current = state.get("current_state", state_name)
        if current in {s.value for s in TERMINAL_STATES}:
            return END
        # Default: return current state as the next node
        return current

    router.__name__ = f"route_{state_name.lower()}"
    return router, {s.value: s.value for s in allowed} | (
        {END: END} if TaskState(state_name) in TERMINAL_STATES else {}
    )


# ── Graph Builder ───────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """
    Construct the compiled LangGraph StateGraph for the 25-state machine.

    Nodes: one per authoritative state (stub logic).
    Edges: conditional, matching ``VALID_TRANSITIONS``.
    Entry: START → SUBMITTED.
    Exit: COMPLETED / CANCELLED → END.
    """
    graph = StateGraph(OrchestratorState)

    # Add one node per authoritative state
    for task_state in TaskState:
        graph.add_node(task_state.value, _make_node(task_state.value))

    # Entry edge
    graph.add_edge(START, TaskState.SUBMITTED.value)

    # Add conditional edges for each non-terminal state
    for task_state in TaskState:
        if task_state in TERMINAL_STATES:
            graph.add_edge(task_state.value, END)
            continue

        allowed = VALID_TRANSITIONS[task_state]
        if not allowed:
            continue

        targets = {s.value: s.value for s in allowed}

        graph.add_conditional_edges(
            task_state.value,
            lambda state, _targets=targets: state.get("current_state", ""),
            targets,
        )

    return graph


# ── Top-Level API ───────────────────────────────────────────────────────


async def create_task(
    title: str,
    description: str | None = None,
    priority: int = 0,
    environment: str = "SANDBOX",
    created_by: str | None = None,
) -> uuid.UUID:
    """
    Create a new task in SUBMITTED state.

    Interface: ``create_task(input) -> task_id`` (PHASE_2_CONTRACTS.md).
    """
    task_id = uuid.uuid4()

    async with get_db_session() as session:
        task = Task(
            id=task_id,
            title=title,
            description=description,
            current_state=TaskState.SUBMITTED.value,
            priority=priority,
            environment=environment,
            created_by=created_by,
        )
        session.add(task)

    logger.info(
        "task.created",
        task_id=str(task_id),
        title=title,
        priority=priority,
        environment=environment,
    )
    return task_id


async def transition(
    task_id: uuid.UUID,
    next_state: str,
    triggered_by: str | None = None,
    reason: str | None = None,
) -> TaskState:
    """
    Transition a task to the next state.

    Interface: ``transition(task_id, next_state)`` (PHASE_2_CONTRACTS.md).

    Runs all guards, records the transition event, and updates the
    checkpoint.
    """
    event_store = EventStore(get_db_session)

    # Load current state
    current_state = await event_store.replay(task_id)

    # Parse and validate target state
    target = TaskStateMachine.parse_state(next_state)

    # Get history for loop detection
    history = await event_store.get_history(task_id)

    # Run guards (state validity, transition validity, loop detection)
    Guards.check_transition_valid(current_state, target)
    Guards.check_loop(target, history)

    # Record the transition (INV-02: persisted before ack)
    await event_store.record_transition(
        task_id=task_id,
        from_state=current_state,
        to_state=target,
        triggered_by=triggered_by,
        reason=reason,
    )

    logger.info(
        "task.transitioned",
        task_id=str(task_id),
        from_state=current_state.value,
        to_state=target.value,
        triggered_by=triggered_by,
    )
    return target


async def replay(task_id: uuid.UUID) -> TaskState:
    """
    Replay a task's event history to derive the current state.

    Interface: ``replay(task_id) -> state`` (PHASE_2_CONTRACTS.md).
    """
    event_store = EventStore(get_db_session)
    state = await event_store.replay(task_id)
    logger.info("task.replayed", task_id=str(task_id), state=state.value)
    return state


async def schedule(task_id: uuid.UUID, priority: int = 0) -> None:
    """
    Schedule a task for execution.

    Interface: ``schedule(task_id, priority)`` (PHASE_2_CONTRACTS.md).
    """
    # Note: TaskScheduler is in-memory.  In production this could be
    # backed by a persistent store.  For Phase 2 we use a module-level
    # instance.
    _scheduler.schedule(task_id, priority)
    logger.info(
        "task.scheduled",
        task_id=str(task_id),
        priority=priority,
        pending=_scheduler.pending_count(),
    )


# Module-level scheduler instance
_scheduler = TaskScheduler()


def get_scheduler() -> TaskScheduler:
    """Return the module-level scheduler.  Useful for tests and inspection."""
    return _scheduler
