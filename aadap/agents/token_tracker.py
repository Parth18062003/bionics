"""
AADAP — Token Accounting
===========================
Per-task token budget enforcement.

Architecture layer: L4 (Agent Layer).
Enforces:
- INV-04: Token budget per task enforced (default 50,000 tokens)

Usage:
    tracker = TokenTracker(task_id=uuid4(), budget=50_000)
    tracker.consume(1200)
    print(tracker.remaining)  # 48800
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from aadap.core.logging import get_logger

logger = get_logger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

DEFAULT_TOKEN_BUDGET = 50_000  # INV-04: default per-task budget


# ── Exceptions ──────────────────────────────────────────────────────────


class TokenBudgetExhaustedError(Exception):
    """Raised when a task's token usage exceeds its budget (INV-04)."""

    def __init__(
        self, task_id: uuid.UUID, tokens_used: int, token_budget: int
    ) -> None:
        self.task_id = task_id
        self.tokens_used = tokens_used
        self.token_budget = token_budget
        super().__init__(
            f"Token budget exhausted for task {task_id}: "
            f"{tokens_used}/{token_budget} tokens used (INV-04)."
        )


# ── Token Tracker ───────────────────────────────────────────────────────


@dataclass
class TokenTracker:
    """
    Per-task token budget accounting.

    Invariant: ``consume()`` will raise ``TokenBudgetExhaustedError``
    when the cumulative usage would exceed the budget.  This is a hard
    stop — no partial consumption.
    """

    task_id: uuid.UUID
    _budget: int = DEFAULT_TOKEN_BUDGET
    _used: int = field(default=0, init=False)

    def consume(self, tokens: int) -> int:
        """
        Record token consumption.

        Parameters
        ----------
        tokens
            Number of tokens consumed (must be > 0).

        Returns
        -------
        int
            Total tokens used after this consumption.

        Raises
        ------
        ValueError
            If ``tokens`` is not positive.
        TokenBudgetExhaustedError
            If consumption would exceed the budget (INV-04).
        """
        if tokens <= 0:
            raise ValueError(f"Token consumption must be positive, got {tokens}")

        projected = self._used + tokens
        if projected > self._budget:
            logger.warning(
                "token_budget.exceeded",
                task_id=str(self.task_id),
                tokens_used=self._used,
                tokens_requested=tokens,
                token_budget=self._budget,
            )
            raise TokenBudgetExhaustedError(
                self.task_id, projected, self._budget
            )

        self._used = projected
        logger.debug(
            "token.consumed",
            task_id=str(self.task_id),
            tokens=tokens,
            total_used=self._used,
            remaining=self.remaining,
        )
        return self._used

    @property
    def remaining(self) -> int:
        """Tokens remaining in the budget."""
        return max(0, self._budget - self._used)

    @property
    def used(self) -> int:
        """Total tokens consumed so far."""
        return self._used

    @property
    def budget(self) -> int:
        """Total token budget for this task."""
        return self._budget

    @property
    def is_exhausted(self) -> bool:
        """Whether the budget has been fully consumed."""
        return self._used >= self._budget

    def to_dict(self) -> dict:
        """Serializable snapshot of current token state."""
        return {
            "task_id": str(self.task_id),
            "budget": self._budget,
            "used": self._used,
            "remaining": self.remaining,
            "is_exhausted": self.is_exhausted,
        }
