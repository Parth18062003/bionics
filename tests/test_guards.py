"""
Phase 2 Tests — Guards & Loop Detection
==========================================
Validates:
- Loop detector allows state entry up to 3 times
- Loop detector raises on 4th entry to same state
- Token budget guard raises when exceeded (INV-04)
- Retry limit guard raises when limit met (INV-03)
- Composite check_all runs all guards
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from aadap.orchestrator.guards import (
    Guards,
    LoopDetectedError,
    LoopDetector,
    RetryLimitExceededError,
    TokenBudgetExceededError,
)
from aadap.orchestrator.state_machine import (
    InvalidStateError,
    InvalidTransitionError,
    TaskState,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_history(entries: list[tuple[str, str]]) -> list[MagicMock]:
    """Build mock history from (from_state, to_state) pairs."""
    result = []
    for i, (fs, ts) in enumerate(entries):
        row = MagicMock()
        row.from_state = fs
        row.to_state = ts
        row.sequence_num = i + 1
        row.created_at = datetime.now(timezone.utc)
        result.append(row)
    return result


# ── Loop Detection ──────────────────────────────────────────────────────


class TestLoopDetector:
    """Verify loop detection limits."""

    def test_allows_first_entry(self):
        """First entry to a state is always allowed."""
        history = _make_history([])
        assert LoopDetector.check(TaskState.PARSING, history) is True

    def test_allows_up_to_three_entries(self):
        """A state can be entered 3 times (limit is 3 entries total)."""
        history = _make_history([
            ("SUBMITTED", "PARSING"),        # entry 1
            ("PARSING", "PARSE_FAILED"),
            ("PARSE_FAILED", "PARSING"),      # entry 2
            ("PARSING", "PARSE_FAILED"),
            ("PARSE_FAILED", "PARSING"),      # entry 3 — this will be the 3rd, so next should fail
        ])
        # Count of PARSING entries: 3 (transitions TO PARSING)
        # Trying a 4th should fail
        with pytest.raises(LoopDetectedError) as exc_info:
            LoopDetector.check(TaskState.PARSING, history)
        assert exc_info.value.count == 3
        assert exc_info.value.limit == 3

    def test_raises_on_fourth_entry(self):
        """4th entry to a state raises LoopDetectedError."""
        history = _make_history([
            ("SUBMITTED", "IN_DEVELOPMENT"),
            ("IN_DEVELOPMENT", "DEV_FAILED"),
            ("DEV_FAILED", "IN_DEVELOPMENT"),
            ("IN_DEVELOPMENT", "DEV_FAILED"),
            ("DEV_FAILED", "IN_DEVELOPMENT"),
        ])
        # IN_DEVELOPMENT entered 3 times already
        with pytest.raises(LoopDetectedError) as exc_info:
            LoopDetector.check(TaskState.IN_DEVELOPMENT, history)
        assert exc_info.value.state == TaskState.IN_DEVELOPMENT

    def test_counts_per_state_independently(self):
        """Different states have independent counters."""
        history = _make_history([
            ("SUBMITTED", "PARSING"),
            ("PARSING", "PARSE_FAILED"),
            ("PARSE_FAILED", "PARSING"),
        ])
        # PARSING entered 2 times, but IN_DEVELOPMENT entered 0 times
        assert LoopDetector.check(TaskState.IN_DEVELOPMENT, history) is True


# ── Token Budget Guard ──────────────────────────────────────────────────


class TestTokenBudgetGuard:
    """Verify INV-04: token budget enforcement."""

    def test_within_budget(self):
        assert Guards.check_token_budget(10_000, 50_000) is True

    def test_at_budget(self):
        assert Guards.check_token_budget(50_000, 50_000) is True

    def test_exceeds_budget(self):
        with pytest.raises(TokenBudgetExceededError) as exc_info:
            Guards.check_token_budget(50_001, 50_000)
        assert exc_info.value.tokens_used == 50_001
        assert exc_info.value.token_budget == 50_000


# ── Retry Limit Guard ──────────────────────────────────────────────────


class TestRetryLimitGuard:
    """Verify INV-03: bounded self-correction."""

    def test_below_limit(self):
        assert Guards.check_retry_limit(0) is True
        assert Guards.check_retry_limit(2) is True

    def test_at_limit(self):
        with pytest.raises(RetryLimitExceededError) as exc_info:
            Guards.check_retry_limit(3)
        assert exc_info.value.retry_count == 3

    def test_above_limit(self):
        with pytest.raises(RetryLimitExceededError):
            Guards.check_retry_limit(5)


# ── State Validation Guard ─────────────────────────────────────────────


class TestStateValidationGuard:
    """Verify non-authoritative states are rejected."""

    def test_valid_state(self):
        result = Guards.check_state_valid("SUBMITTED")
        assert result == TaskState.SUBMITTED

    def test_invalid_state(self):
        with pytest.raises(InvalidStateError):
            Guards.check_state_valid("BOGUS_STATE")


# ── Transition Validation Guard ─────────────────────────────────────────


class TestTransitionValidationGuard:
    """Verify transition guard delegates to state machine."""

    def test_valid_transition(self):
        assert Guards.check_transition_valid(
            TaskState.SUBMITTED, TaskState.PARSING
        ) is True

    def test_invalid_transition(self):
        with pytest.raises(InvalidTransitionError):
            Guards.check_transition_valid(
                TaskState.SUBMITTED, TaskState.DEPLOYED
            )


# ── Composite check_all ─────────────────────────────────────────────────


class TestCompositeGuard:
    """Verify check_all runs all guards together."""

    def test_all_pass(self):
        history = _make_history([])
        from_s, to_s = Guards.check_all(
            from_state="SUBMITTED",
            to_state="PARSING",
            history=history,
            tokens_used=100,
            token_budget=50_000,
            retry_count=0,
        )
        assert from_s == TaskState.SUBMITTED
        assert to_s == TaskState.PARSING

    def test_fails_on_invalid_state(self):
        with pytest.raises(InvalidStateError):
            Guards.check_all(
                from_state="BOGUS",
                to_state="PARSING",
                history=[],
            )

    def test_fails_on_invalid_transition(self):
        with pytest.raises(InvalidTransitionError):
            Guards.check_all(
                from_state="SUBMITTED",
                to_state="DEPLOYED",
                history=[],
            )

    def test_fails_on_loop(self):
        history = _make_history([
            ("SUBMITTED", "PARSING"),
            ("PARSING", "PARSE_FAILED"),
            ("PARSE_FAILED", "PARSING"),
            ("PARSING", "PARSE_FAILED"),
            ("PARSE_FAILED", "PARSING"),
        ])
        with pytest.raises(LoopDetectedError):
            Guards.check_all(
                from_state="PARSE_FAILED",
                to_state="PARSING",
                history=history,
            )

    def test_fails_on_token_budget(self):
        with pytest.raises(TokenBudgetExceededError):
            Guards.check_all(
                from_state="SUBMITTED",
                to_state="PARSING",
                history=[],
                tokens_used=100_000,
                token_budget=50_000,
            )

    def test_fails_on_retry_limit(self):
        with pytest.raises(RetryLimitExceededError):
            Guards.check_all(
                from_state="SUBMITTED",
                to_state="PARSING",
                history=[],
                retry_count=3,
            )
