"""
AADAP — Task State Machine
============================
Deterministic 25-state machine governing the task lifecycle.

Architecture layer: L5 (Orchestration).
Source of truth: ARCHITECTURE.md §Authoritative Task State Machine.

Invariants enforced:
- Only AUTHORITATIVE states may exist
- Undefined transitions are P0 bugs (raises InvalidTransitionError)
"""

from __future__ import annotations

from enum import StrEnum


# ── Authoritative Task States ───────────────────────────────────────────
# 25 states.  START / END are implicit non-states (ARCHITECTURE.md).


class TaskState(StrEnum):
    """Authoritative task states (STATE_SET_VERSION: v1.0)."""

    SUBMITTED = "SUBMITTED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    PARSE_FAILED = "PARSE_FAILED"
    PLANNING = "PLANNING"
    PLANNED = "PLANNED"
    AGENT_ASSIGNMENT = "AGENT_ASSIGNMENT"
    AGENT_ASSIGNED = "AGENT_ASSIGNED"
    IN_DEVELOPMENT = "IN_DEVELOPMENT"
    CODE_GENERATED = "CODE_GENERATED"
    DEV_FAILED = "DEV_FAILED"
    IN_VALIDATION = "IN_VALIDATION"
    VALIDATION_PASSED = "VALIDATION_PASSED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    OPTIMIZATION_PENDING = "OPTIMIZATION_PENDING"
    IN_OPTIMIZATION = "IN_OPTIMIZATION"
    OPTIMIZED = "OPTIMIZED"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# ── Terminal states (no outgoing transitions) ───────────────────────────

TERMINAL_STATES: frozenset[TaskState] = frozenset(
    {TaskState.COMPLETED, TaskState.CANCELLED}
)


# ── Authoritative Transition Map ────────────────────────────────────────
# Exhaustive forward-transition whitelist.
# Any transition not listed here is INVALID (P0 bug).

VALID_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.SUBMITTED: frozenset(
        {TaskState.PARSING, TaskState.CANCELLED}
    ),
    TaskState.PARSING: frozenset(
        {TaskState.PARSED, TaskState.PARSE_FAILED}
    ),
    TaskState.PARSED: frozenset(
        {TaskState.PLANNING, TaskState.CANCELLED}
    ),
    TaskState.PARSE_FAILED: frozenset(
        {TaskState.PARSING, TaskState.CANCELLED}
    ),
    TaskState.PLANNING: frozenset(
        {TaskState.PLANNED, TaskState.CANCELLED}
    ),
    TaskState.PLANNED: frozenset(
        {TaskState.AGENT_ASSIGNMENT, TaskState.CANCELLED}
    ),
    TaskState.AGENT_ASSIGNMENT: frozenset(
        {TaskState.AGENT_ASSIGNED, TaskState.CANCELLED}
    ),
    TaskState.AGENT_ASSIGNED: frozenset(
        {TaskState.IN_DEVELOPMENT, TaskState.CANCELLED}
    ),
    TaskState.IN_DEVELOPMENT: frozenset(
        {TaskState.CODE_GENERATED, TaskState.DEV_FAILED}
    ),
    TaskState.CODE_GENERATED: frozenset(
        {TaskState.IN_VALIDATION, TaskState.CANCELLED}
    ),
    TaskState.DEV_FAILED: frozenset(
        {TaskState.IN_DEVELOPMENT, TaskState.CANCELLED}
    ),
    TaskState.IN_VALIDATION: frozenset(
        {TaskState.VALIDATION_PASSED, TaskState.VALIDATION_FAILED}
    ),
    TaskState.VALIDATION_PASSED: frozenset(
        {TaskState.OPTIMIZATION_PENDING, TaskState.APPROVAL_PENDING}
    ),
    TaskState.VALIDATION_FAILED: frozenset(
        {TaskState.IN_DEVELOPMENT, TaskState.CANCELLED}
    ),
    TaskState.OPTIMIZATION_PENDING: frozenset(
        {TaskState.IN_OPTIMIZATION, TaskState.CANCELLED}
    ),
    TaskState.IN_OPTIMIZATION: frozenset(
        {TaskState.OPTIMIZED, TaskState.CANCELLED}
    ),
    TaskState.OPTIMIZED: frozenset(
        {TaskState.APPROVAL_PENDING, TaskState.CANCELLED}
    ),
    TaskState.APPROVAL_PENDING: frozenset(
        {TaskState.IN_REVIEW}
    ),
    TaskState.IN_REVIEW: frozenset(
        {TaskState.APPROVED, TaskState.REJECTED}
    ),
    TaskState.APPROVED: frozenset(
        {TaskState.DEPLOYING, TaskState.CANCELLED}
    ),
    TaskState.REJECTED: frozenset(
        {TaskState.IN_DEVELOPMENT, TaskState.CANCELLED}
    ),
    TaskState.DEPLOYING: frozenset(
        {TaskState.DEPLOYED, TaskState.DEV_FAILED}
    ),
    TaskState.DEPLOYED: frozenset(
        {TaskState.COMPLETED}
    ),
    # Terminal states — no outgoing transitions
    TaskState.COMPLETED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}


# ── Exceptions ──────────────────────────────────────────────────────────


class InvalidStateError(Exception):
    """Raised when a non-authoritative state is encountered."""

    def __init__(self, state: str) -> None:
        self.state = state
        super().__init__(
            f"Non-authoritative state '{state}'. "
            f"Only the 25 authoritative states are valid."
        )


class InvalidTransitionError(Exception):
    """Raised when an undefined transition is attempted (P0 bug)."""

    def __init__(self, from_state: TaskState, to_state: TaskState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        allowed = VALID_TRANSITIONS.get(from_state, frozenset())
        super().__init__(
            f"Invalid transition {from_state.value} → {to_state.value}. "
            f"Allowed: {sorted(s.value for s in allowed)}."
        )


# ── State Machine ───────────────────────────────────────────────────────


class TaskStateMachine:
    """
    Deterministic state machine for AADAP task lifecycle.

    All 25 authoritative states are represented.  Any other state string
    is rejected.  Undefined transitions raise ``InvalidTransitionError``
    (P0 bug per PHASE_2_CONTRACTS.md).
    """

    @staticmethod
    def parse_state(raw: str) -> TaskState:
        """
        Convert a raw string to a ``TaskState``.

        Raises ``InvalidStateError`` if the string doesn't match any
        authoritative state.
        """
        try:
            return TaskState(raw)
        except ValueError:
            raise InvalidStateError(raw) from None

    @staticmethod
    def validate_transition(from_state: TaskState, to_state: TaskState) -> bool:
        """
        Return ``True`` if the transition is valid.

        Raises ``InvalidTransitionError`` if the transition is undefined.
        """
        allowed = VALID_TRANSITIONS.get(from_state)
        if allowed is None:
            raise InvalidStateError(from_state)
        if to_state not in allowed:
            raise InvalidTransitionError(from_state, to_state)
        return True

    @staticmethod
    def get_allowed_transitions(state: TaskState) -> frozenset[TaskState]:
        """Return the set of valid next states for the given state."""
        allowed = VALID_TRANSITIONS.get(state)
        if allowed is None:
            raise InvalidStateError(state)
        return allowed

    @staticmethod
    def is_terminal(state: TaskState) -> bool:
        """Return ``True`` if the state is terminal (no outgoing transitions)."""
        return state in TERMINAL_STATES
