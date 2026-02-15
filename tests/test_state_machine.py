"""
Phase 2 Tests — State Machine
================================
Validates:
- All 25 authoritative states exist
- Valid transitions accepted
- Invalid transitions raise InvalidTransitionError
- Non-authoritative state strings rejected
- Terminal states have no outgoing transitions
"""

from __future__ import annotations

import pytest

from aadap.db.models import TASK_STATES
from aadap.orchestrator.state_machine import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    InvalidStateError,
    InvalidTransitionError,
    TaskState,
    TaskStateMachine,
)


# ── Completeness ────────────────────────────────────────────────────────


class TestStateCompleteness:
    """Verify the enum and transition map match ARCHITECTURE.md."""

    def test_all_25_states_exist(self):
        """TaskState enum has exactly 25 members."""
        assert len(TaskState) == 25

    def test_enum_matches_models_task_states(self):
        """TaskState enum is in sync with TASK_STATES from models.py."""
        enum_values = {s.value for s in TaskState}
        model_values = set(TASK_STATES)
        assert enum_values == model_values

    def test_transition_map_covers_all_states(self):
        """Every state appears as a key in VALID_TRANSITIONS."""
        for state in TaskState:
            assert state in VALID_TRANSITIONS, (
                f"State {state.value} missing from VALID_TRANSITIONS"
            )

    def test_transition_targets_are_valid_states(self):
        """All target states in VALID_TRANSITIONS are authoritative."""
        for source, targets in VALID_TRANSITIONS.items():
            for target in targets:
                assert isinstance(target, TaskState), (
                    f"Target {target} from {source.value} is not a TaskState"
                )


# ── Valid Transitions ───────────────────────────────────────────────────


class TestValidTransitions:
    """Verify the transition whitelist works correctly."""

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            (TaskState.SUBMITTED, TaskState.PARSING),
            (TaskState.SUBMITTED, TaskState.CANCELLED),
            (TaskState.PARSING, TaskState.PARSED),
            (TaskState.PARSING, TaskState.PARSE_FAILED),
            (TaskState.PARSED, TaskState.PLANNING),
            (TaskState.PARSE_FAILED, TaskState.PARSING),  # retry
            (TaskState.PLANNING, TaskState.PLANNED),
            (TaskState.PLANNED, TaskState.AGENT_ASSIGNMENT),
            (TaskState.AGENT_ASSIGNMENT, TaskState.AGENT_ASSIGNED),
            (TaskState.AGENT_ASSIGNED, TaskState.IN_DEVELOPMENT),
            (TaskState.IN_DEVELOPMENT, TaskState.CODE_GENERATED),
            (TaskState.IN_DEVELOPMENT, TaskState.DEV_FAILED),
            (TaskState.CODE_GENERATED, TaskState.IN_VALIDATION),
            (TaskState.DEV_FAILED, TaskState.IN_DEVELOPMENT),  # retry
            (TaskState.IN_VALIDATION, TaskState.VALIDATION_PASSED),
            (TaskState.IN_VALIDATION, TaskState.VALIDATION_FAILED),
            (TaskState.VALIDATION_PASSED, TaskState.OPTIMIZATION_PENDING),
            (TaskState.VALIDATION_PASSED, TaskState.APPROVAL_PENDING),
            (TaskState.VALIDATION_FAILED, TaskState.IN_DEVELOPMENT),  # retry
            (TaskState.OPTIMIZATION_PENDING, TaskState.IN_OPTIMIZATION),
            (TaskState.IN_OPTIMIZATION, TaskState.OPTIMIZED),
            (TaskState.OPTIMIZED, TaskState.APPROVAL_PENDING),
            (TaskState.APPROVAL_PENDING, TaskState.IN_REVIEW),
            (TaskState.IN_REVIEW, TaskState.APPROVED),
            (TaskState.IN_REVIEW, TaskState.REJECTED),
            (TaskState.APPROVED, TaskState.DEPLOYING),
            (TaskState.REJECTED, TaskState.IN_DEVELOPMENT),  # rework
            (TaskState.DEPLOYING, TaskState.DEPLOYED),
            (TaskState.DEPLOYING, TaskState.DEV_FAILED),
            (TaskState.DEPLOYED, TaskState.COMPLETED),
        ],
    )
    def test_valid_transition_accepted(self, from_state, to_state):
        """Each transition in the whitelist returns True."""
        assert TaskStateMachine.validate_transition(from_state, to_state) is True

    @pytest.mark.parametrize(
        "from_state,to_state",
        [
            (TaskState.SUBMITTED, TaskState.IN_DEVELOPMENT),
            (TaskState.COMPLETED, TaskState.SUBMITTED),
            (TaskState.CANCELLED, TaskState.SUBMITTED),
            (TaskState.PARSING, TaskState.DEPLOYING),
            (TaskState.APPROVAL_PENDING, TaskState.DEPLOYED),
            (TaskState.IN_REVIEW, TaskState.COMPLETED),
            (TaskState.DEPLOYED, TaskState.SUBMITTED),
        ],
    )
    def test_invalid_transitions_rejected(self, from_state, to_state):
        """Illegal transitions raise InvalidTransitionError (P0)."""
        with pytest.raises(InvalidTransitionError) as exc_info:
            TaskStateMachine.validate_transition(from_state, to_state)
        assert exc_info.value.from_state == from_state
        assert exc_info.value.to_state == to_state


# ── State Parsing ───────────────────────────────────────────────────────


class TestStateParsing:
    """Verify parse_state validates raw strings."""

    def test_valid_state_parsed(self):
        assert TaskStateMachine.parse_state("SUBMITTED") == TaskState.SUBMITTED

    def test_all_states_parseable(self):
        for state_str in TASK_STATES:
            result = TaskStateMachine.parse_state(state_str)
            assert result.value == state_str

    def test_invalid_state_rejected(self):
        with pytest.raises(InvalidStateError):
            TaskStateMachine.parse_state("NONEXISTENT_STATE")

    def test_empty_string_rejected(self):
        with pytest.raises(InvalidStateError):
            TaskStateMachine.parse_state("")


# ── Terminal States ─────────────────────────────────────────────────────


class TestTerminalStates:
    """Terminal states have no outgoing transitions."""

    def test_completed_is_terminal(self):
        assert TaskStateMachine.is_terminal(TaskState.COMPLETED) is True
        assert TaskStateMachine.get_allowed_transitions(TaskState.COMPLETED) == frozenset()

    def test_cancelled_is_terminal(self):
        assert TaskStateMachine.is_terminal(TaskState.CANCELLED) is True
        assert TaskStateMachine.get_allowed_transitions(TaskState.CANCELLED) == frozenset()

    def test_submitted_is_not_terminal(self):
        assert TaskStateMachine.is_terminal(TaskState.SUBMITTED) is False

    def test_only_two_terminal_states(self):
        assert TERMINAL_STATES == frozenset({TaskState.COMPLETED, TaskState.CANCELLED})


# ── get_allowed_transitions ─────────────────────────────────────────────


class TestGetAllowedTransitions:
    """Verify transition lookup."""

    def test_submitted_has_two_targets(self):
        allowed = TaskStateMachine.get_allowed_transitions(TaskState.SUBMITTED)
        assert allowed == frozenset({TaskState.PARSING, TaskState.CANCELLED})

    def test_approval_pending_has_one_target(self):
        allowed = TaskStateMachine.get_allowed_transitions(TaskState.APPROVAL_PENDING)
        assert allowed == frozenset({TaskState.IN_REVIEW})
