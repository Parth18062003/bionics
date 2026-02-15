"""
AADAP — Loop Detection & Invariant Guards
============================================
Safety guards that enforce system invariants during orchestration.

Architecture layer: L5 (Orchestration).
Enforces:
- INV-03: Agent self-correction loops bounded (max 3 attempts)
- INV-04: Token budget per task enforced (default 50,000 tokens)
- Same state may not be entered >3 times (PHASE_2_CONTRACTS.md)
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from aadap.orchestrator.state_machine import (
    InvalidStateError,
    TaskState,
    TaskStateMachine,
)

if TYPE_CHECKING:
    from aadap.db.models import StateTransition


# ── Constants ───────────────────────────────────────────────────────────

MAX_STATE_ENTRIES = 3       # Same state may not be entered >3 times
MAX_RETRY_COUNT = 3         # INV-03: bounded self-correction


# ── Exceptions ──────────────────────────────────────────────────────────


class LoopDetectedError(Exception):
    """Raised when a state has been entered too many times."""

    def __init__(self, state: TaskState, count: int, limit: int) -> None:
        self.state = state
        self.count = count
        self.limit = limit
        super().__init__(
            f"Loop detected: state '{state.value}' has been entered "
            f"{count} time(s), limit is {limit}."
        )


class TokenBudgetExceededError(Exception):
    """Raised when a task's token usage exceeds its budget (INV-04)."""

    def __init__(self, tokens_used: int, token_budget: int) -> None:
        self.tokens_used = tokens_used
        self.token_budget = token_budget
        super().__init__(
            f"Token budget exceeded: {tokens_used}/{token_budget} "
            f"tokens used (INV-04)."
        )


class RetryLimitExceededError(Exception):
    """Raised when a task has exceeded its retry limit (INV-03)."""

    def __init__(self, retry_count: int, limit: int) -> None:
        self.retry_count = retry_count
        self.limit = limit
        super().__init__(
            f"Retry limit exceeded: {retry_count}/{limit} attempts (INV-03)."
        )


# ── Loop Detector ───────────────────────────────────────────────────────


class LoopDetector:
    """
    Detects and prevents state re-entry loops.

    Contract: same state may not be entered >3 times during a task's
    lifetime (PHASE_2_CONTRACTS.md).
    """

    @staticmethod
    def check(
        target_state: TaskState,
        history: list[StateTransition],
        limit: int = MAX_STATE_ENTRIES,
    ) -> bool:
        """
        Return ``True`` if transitioning to ``target_state`` is safe.

        Raises ``LoopDetectedError`` if the target state has already
        been entered ``limit`` times in the history.
        """
        entry_count = sum(
            1 for t in history if t.to_state == target_state.value
        )
        if entry_count >= limit:
            raise LoopDetectedError(target_state, entry_count, limit)
        return True


# ── Invariant Guards ────────────────────────────────────────────────────


class Guards:
    """
    Composite guard that checks all relevant invariants before
    allowing a state transition.
    """

    @staticmethod
    def check_state_valid(state: str) -> TaskState:
        """
        Validate that a raw state string is authoritative.

        Returns the parsed ``TaskState``.
        Raises ``InvalidStateError`` if not.
        """
        return TaskStateMachine.parse_state(state)

    @staticmethod
    def check_transition_valid(
        from_state: TaskState, to_state: TaskState
    ) -> bool:
        """
        Validate the transition against the authoritative whitelist.

        Raises ``InvalidTransitionError``.
        """
        return TaskStateMachine.validate_transition(from_state, to_state)

    @staticmethod
    def check_token_budget(tokens_used: int, token_budget: int) -> bool:
        """
        Enforce INV-04: token budget per task.

        Raises ``TokenBudgetExceededError`` if budget is exhausted.
        """
        if tokens_used > token_budget:
            raise TokenBudgetExceededError(tokens_used, token_budget)
        return True

    @staticmethod
    def check_retry_limit(
        retry_count: int, limit: int = MAX_RETRY_COUNT
    ) -> bool:
        """
        Enforce INV-03: bounded self-correction.

        Raises ``RetryLimitExceededError`` if limit is reached.
        """
        if retry_count >= limit:
            raise RetryLimitExceededError(retry_count, limit)
        return True

    @staticmethod
    def check_loop(
        target_state: TaskState,
        history: list[StateTransition],
    ) -> bool:
        """
        Enforce: same state not entered >3 times.

        Raises ``LoopDetectedError``.
        """
        return LoopDetector.check(target_state, history)

    @classmethod
    def check_all(
        cls,
        from_state: str,
        to_state: str,
        history: list[StateTransition],
        tokens_used: int = 0,
        token_budget: int = 50_000,
        retry_count: int = 0,
    ) -> tuple[TaskState, TaskState]:
        """
        Run all guard checks.  Returns parsed (from_state, to_state).

        Raises the first invariant violation found.
        """
        parsed_from = cls.check_state_valid(from_state)
        parsed_to = cls.check_state_valid(to_state)
        cls.check_transition_valid(parsed_from, parsed_to)
        cls.check_loop(parsed_to, history)
        cls.check_token_budget(tokens_used, token_budget)
        cls.check_retry_limit(retry_count)
        return parsed_from, parsed_to
