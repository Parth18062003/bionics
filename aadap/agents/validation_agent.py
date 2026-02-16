"""
AADAP — Validation Agent
============================
Code validation agent: static analysis, pattern matching, risk scoring.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_4_CONTRACTS.md, ARCHITECTURE.md §Safety Architecture.

Maps to Safety Gates 1-3:
  Gate 1: Static analysis (AST)
  Gate 2: Pattern matching
  Gate 3: Semantic risk scoring
  Gate 4: Human approval (out of Phase 4 scope)

Invariants enforced:
- INV-03: Max 3 self-correction attempts
- INV-04: Token budget per task (via TokenTracker)
- INV-06: Audit trail via structured logging
- INV-07: All generated code must pass validation before deployment
"""

from __future__ import annotations

from typing import Any

from aadap.agents.base import AgentContext, AgentResult, BaseAgent
from aadap.agents.prompts.base import (
    OutputSchemaViolation,
    build_correction_prompt,
    validate_output,
)
from aadap.agents.prompts.validation import (
    VALIDATION_REPORT_SCHEMA,
    VALIDATION_REVIEW_PROMPT,
)
from aadap.agents.token_tracker import TokenBudgetExhaustedError
from aadap.core.logging import get_logger
from aadap.integrations.llm_client import BaseLLMClient

logger = get_logger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

MAX_SELF_CORRECTIONS = 3  # INV-03
DEFAULT_MODEL = "gpt-4o-mini"


# ── ValidationAgent ────────────────────────────────────────────────────


class ValidationAgent(BaseAgent):
    """
    Code validation agent performing safety analysis and risk scoring.

    Implements Safety Gates 1-3 via LLM-based analysis.
    Returns a structured validation report with is_valid, issues,
    risk_score, and recommendation.
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
            agent_type="validation",
            **kwargs,
        )
        self._llm_client = llm_client
        self._model = model

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        """
        Validate code and produce a structured safety report.

        Self-corrects up to MAX_SELF_CORRECTIONS on schema failures.
        Escalates on token exhaustion or persistent failures.
        """
        task_data = context.task_data
        prompt = VALIDATION_REVIEW_PROMPT.render({
            "code": task_data.get("code", ""),
            "language": task_data.get("language", "python"),
            "task_description": task_data.get("description", ""),
            "environment": task_data.get("environment", "SANDBOX"),
        })

        total_tokens = 0

        for attempt in range(1, MAX_SELF_CORRECTIONS + 1):
            logger.info(
                "validation.attempt",
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
                    "validation.llm_error",
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
                    "validation.token_budget_exhausted",
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
                    response.content, VALIDATION_REPORT_SCHEMA
                )

                # Additional domain validation: risk_score bounds
                risk_score = result.get("risk_score")
                if isinstance(risk_score, (int, float)):
                    if not (0.0 <= float(risk_score) <= 1.0):
                        raise OutputSchemaViolation(
                            errors=["risk_score must be between 0.0 and 1.0, "
                                    f"got {risk_score}"],
                            raw_output=response.content,
                        )

                # Additional domain validation: recommendation values
                recommendation = result.get("recommendation", "")
                valid_recommendations = {"approve", "revise", "reject"}
                if recommendation not in valid_recommendations:
                    raise OutputSchemaViolation(
                        errors=[
                            f"recommendation must be one of "
                            f"{sorted(valid_recommendations)}, "
                            f"got '{recommendation}'"
                        ],
                        raw_output=response.content,
                    )

                logger.info(
                    "validation.success",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    attempt=attempt,
                    tokens_used=total_tokens,
                    is_valid=result.get("is_valid"),
                    risk_score=risk_score,
                )
                return AgentResult(
                    success=True,
                    output=result,
                    tokens_used=total_tokens,
                    artifacts=[{
                        "type": "validation_report",
                        "content": result,
                    }],
                )
            except OutputSchemaViolation as e:
                logger.warning(
                    "validation.schema_violation",
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
