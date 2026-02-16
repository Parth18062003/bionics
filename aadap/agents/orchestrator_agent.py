"""
AADAP — Orchestrator Agent
==============================
Decision-logic agent: decomposes tasks and assigns sub-tasks to
specialist agents.

Architecture layer: L4 (Agent Layer).
Source of truth: PHASE_4_CONTRACTS.md §Agents in Scope.

Invariants enforced:
- INV-03: Max 3 self-correction attempts
- INV-04: Token budget per task (via TokenTracker)
- INV-06: Audit trail via structured logging
- No direct execution without orchestrator authorization

Design decisions:
- The orchestrator agent is itself an agent — it does NOT self-assign.
  It produces routing decisions that the L5 orchestration layer consumes.
- Uses MockLLMClient by default; real LLM wired in later phases.
"""

from __future__ import annotations

import json
from typing import Any

from aadap.agents.base import AgentContext, AgentResult, BaseAgent
from aadap.agents.prompts.base import (
    OutputSchemaViolation,
    build_correction_prompt,
    validate_output,
)
from aadap.agents.prompts.orchestrator import (
    ORCHESTRATOR_DECISION_PROMPT,
    ORCHESTRATOR_DECISION_SCHEMA,
)
from aadap.agents.token_tracker import TokenBudgetExhaustedError
from aadap.core.logging import get_logger
from aadap.integrations.llm_client import BaseLLMClient

logger = get_logger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

MAX_SELF_CORRECTIONS = 3  # INV-03: hard upper bound
DEFAULT_MODEL = "gpt-4o"


# ── OrchestratorAgent ──────────────────────────────────────────────────


class OrchestratorAgent(BaseAgent):
    """
    Decision-logic agent that decomposes tasks and routes to specialists.

    Does NOT execute tasks directly — it produces structured assignment
    decisions consumed by the L5 orchestration layer.
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
            agent_type="orchestrator",
            **kwargs,
        )
        self._llm_client = llm_client
        self._model = model

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        """
        Produce a task routing decision.

        Self-corrects up to MAX_SELF_CORRECTIONS times on schema failures.
        Escalates on token exhaustion or persistent schema violations.
        """
        task_data = context.task_data
        prompt = ORCHESTRATOR_DECISION_PROMPT.render({
            "title": task_data.get("title", ""),
            "description": task_data.get("description", ""),
            "environment": task_data.get("environment", "SANDBOX"),
        })

        total_tokens = 0

        for attempt in range(1, MAX_SELF_CORRECTIONS + 1):
            logger.info(
                "orchestrator.attempt",
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
                    "orchestrator.llm_error",
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
                    "orchestrator.token_budget_exhausted",
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

            # Validate output against schema
            try:
                result = validate_output(
                    response.content, ORCHESTRATOR_DECISION_SCHEMA
                )
                logger.info(
                    "orchestrator.success",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    attempt=attempt,
                    tokens_used=total_tokens,
                )
                return AgentResult(
                    success=True,
                    output=result,
                    tokens_used=total_tokens,
                    artifacts=[{
                        "type": "routing_decision",
                        "content": result,
                    }],
                )
            except OutputSchemaViolation as e:
                logger.warning(
                    "orchestrator.schema_violation",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    attempt=attempt,
                    errors=e.errors,
                )
                if attempt == MAX_SELF_CORRECTIONS:
                    # INV-03: exhausted retries → escalate
                    return AgentResult(
                        success=False,
                        error=(
                            f"ESCALATE: Schema validation failed after "
                            f"{MAX_SELF_CORRECTIONS} attempts (INV-03). "
                            f"Last errors: {e.errors}"
                        ),
                        tokens_used=total_tokens,
                    )
                # Self-correct: build a correction prompt
                prompt = build_correction_prompt(
                    prompt, response.content, e
                )

        # Should not reach here, but defensive
        return AgentResult(
            success=False,
            error="ESCALATE: Unexpected loop exit",
            tokens_used=total_tokens,
        )
