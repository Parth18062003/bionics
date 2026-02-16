"""
AADAP — Optimization Agent (PySpark)
========================================
PySpark performance optimization agent.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_4_CONTRACTS.md §Agents in Scope.

Invariants enforced:
- INV-03: Max 3 self-correction attempts
- INV-04: Token budget per task (via TokenTracker)
- INV-06: Audit trail via structured logging
"""

from __future__ import annotations

from typing import Any

from aadap.agents.base import AgentContext, AgentResult, BaseAgent
from aadap.agents.prompts.base import (
    OutputSchemaViolation,
    build_correction_prompt,
    validate_output,
)
from aadap.agents.prompts.optimization import (
    OPTIMIZATION_OPTIMIZE_PROMPT,
    OPTIMIZATION_OUTPUT_SCHEMA,
)
from aadap.agents.token_tracker import TokenBudgetExhaustedError
from aadap.core.logging import get_logger
from aadap.integrations.llm_client import BaseLLMClient

logger = get_logger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

MAX_SELF_CORRECTIONS = 3  # INV-03
DEFAULT_MODEL = "gpt-4o"


# ── OptimizationAgent ─────────────────────────────────────────────────


class OptimizationAgent(BaseAgent):
    """
    PySpark optimization agent: partitioning, caching, broadcast joins,
    predicate pushdown, and shuffle reduction.

    Receives existing PySpark code and produces an optimized version
    with a changelog of improvements.
    """

    def __init__(
        self,
        agent_id: str,
        llm_client: BaseLLMClient,
        model: str = DEFAULT_MODEL,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            agent_type="optimization",
            **kwargs,
        )
        self._llm_client = llm_client
        self._model = model

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        """
        Optimize PySpark code for performance.

        Self-corrects up to MAX_SELF_CORRECTIONS on schema failures.
        Escalates on token exhaustion or persistent failures.
        """
        task_data = context.task_data
        prompt = OPTIMIZATION_OPTIMIZE_PROMPT.render({
            "code": task_data.get("code", ""),
            "context": task_data.get("context", "None"),
            "environment": task_data.get("environment", "SANDBOX"),
        })

        total_tokens = 0

        for attempt in range(1, MAX_SELF_CORRECTIONS + 1):
            logger.info(
                "optimization.attempt",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                attempt=attempt,
                max_attempts=MAX_SELF_CORRECTIONS,
            )

            try:
                response = await self._llm_client.complete(
                    prompt=prompt,
                    model=self._model,
                )
            except Exception as exc:
                logger.error(
                    "optimization.llm_error",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    error=str(exc),
                )
                return AgentResult(
                    success=False,
                    error=f"ESCALATE: LLM call failed: {exc}",
                    tokens_used=total_tokens,
                )

            # Track tokens (INV-04)
            try:
                self._token_tracker.consume(response.tokens_used)
            except TokenBudgetExhaustedError:
                logger.warning(
                    "optimization.token_budget_exhausted",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    tokens_used=total_tokens + response.tokens_used,
                )
                return AgentResult(
                    success=False,
                    error="ESCALATE: Token budget exhausted (INV-04)",
                    tokens_used=total_tokens + response.tokens_used,
                )

            total_tokens += response.tokens_used

            # Validate output
            try:
                result = validate_output(
                    response.content, OPTIMIZATION_OUTPUT_SCHEMA
                )
                logger.info(
                    "optimization.success",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    attempt=attempt,
                    tokens_used=total_tokens,
                    changes_count=len(result.get("changes", [])),
                )
                return AgentResult(
                    success=True,
                    output=result,
                    tokens_used=total_tokens,
                    artifacts=[{
                        "type": "optimized_code",
                        "content": result,
                    }],
                )
            except OutputSchemaViolation as e:
                logger.warning(
                    "optimization.schema_violation",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    attempt=attempt,
                    errors=e.errors,
                )
                if attempt == MAX_SELF_CORRECTIONS:
                    return AgentResult(
                        success=False,
                        error=(
                            f"ESCALATE: Schema validation failed after "
                            f"{MAX_SELF_CORRECTIONS} attempts (INV-03). "
                            f"Last errors: {e.errors}"
                        ),
                        tokens_used=total_tokens,
                    )
                prompt = build_correction_prompt(
                    prompt, response.content, e
                )

        # Defensive
        return AgentResult(
            success=False,
            error="ESCALATE: Unexpected loop exit",
            tokens_used=total_tokens,
        )
