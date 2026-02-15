"""
AADAP — Token Tracker Tests
================================
Validates:
- Consume within budget succeeds
- Consume exceeding budget raises TokenBudgetExhaustedError
- Properties report correct values
- Default budget is 50,000 (INV-04)
- Zero remaining after exhaustion
"""

from __future__ import annotations

import uuid

import pytest

from aadap.agents.token_tracker import (
    DEFAULT_TOKEN_BUDGET,
    TokenBudgetExhaustedError,
    TokenTracker,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def task_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def tracker(task_id: uuid.UUID) -> TokenTracker:
    return TokenTracker(task_id=task_id)


# ── Tests ────────────────────────────────────────────────────────────────


class TestTokenBudgetDefaults:
    """Default budget matches INV-04."""

    def test_default_budget_is_50000(self, tracker: TokenTracker):
        assert tracker.budget == 50_000
        assert DEFAULT_TOKEN_BUDGET == 50_000

    def test_initial_used_is_zero(self, tracker: TokenTracker):
        assert tracker.used == 0

    def test_initial_remaining_equals_budget(self, tracker: TokenTracker):
        assert tracker.remaining == 50_000

    def test_not_exhausted_initially(self, tracker: TokenTracker):
        assert tracker.is_exhausted is False


class TestTokenConsumption:
    """Consume tokens within and beyond budget."""

    def test_consume_within_budget(self, tracker: TokenTracker):
        total = tracker.consume(1000)
        assert total == 1000
        assert tracker.used == 1000
        assert tracker.remaining == 49_000

    def test_consume_multiple_times(self, tracker: TokenTracker):
        tracker.consume(10_000)
        tracker.consume(20_000)
        assert tracker.used == 30_000
        assert tracker.remaining == 20_000

    def test_consume_exact_budget(self, tracker: TokenTracker):
        tracker.consume(50_000)
        assert tracker.used == 50_000
        assert tracker.remaining == 0
        assert tracker.is_exhausted is True

    def test_consume_exceeds_budget_raises(self, tracker: TokenTracker):
        with pytest.raises(TokenBudgetExhaustedError, match="INV-04"):
            tracker.consume(50_001)

    def test_consume_after_partial_exceeds(self, tracker: TokenTracker):
        tracker.consume(40_000)
        with pytest.raises(TokenBudgetExhaustedError):
            tracker.consume(10_001)
        # Usage should NOT have increased (hard stop)
        assert tracker.used == 40_000

    def test_consume_zero_raises(self, tracker: TokenTracker):
        with pytest.raises(ValueError, match="positive"):
            tracker.consume(0)

    def test_consume_negative_raises(self, tracker: TokenTracker):
        with pytest.raises(ValueError, match="positive"):
            tracker.consume(-100)


class TestCustomBudget:
    """Custom token budget."""

    def test_custom_budget(self, task_id: uuid.UUID):
        tracker = TokenTracker(task_id=task_id, _budget=10_000)
        assert tracker.budget == 10_000
        tracker.consume(10_000)
        assert tracker.is_exhausted is True


class TestSerialization:
    """to_dict() snapshot."""

    def test_to_dict(self, tracker: TokenTracker, task_id: uuid.UUID):
        tracker.consume(5_000)
        d = tracker.to_dict()
        assert d["task_id"] == str(task_id)
        assert d["budget"] == 50_000
        assert d["used"] == 5_000
        assert d["remaining"] == 45_000
        assert d["is_exhausted"] is False
