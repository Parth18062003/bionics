"""
AADAP — Ingestion Agent
===========================
Code-generation **and execution** agent for data ingestion workloads
on Azure Databricks and Microsoft Fabric.

Architecture layer: L4 (Agent Layer).
Follows FabricAgent conventions: prompt → LLM → validate → (optionally) execute.

Supports three ingestion modes via dedicated prompt templates:
- **batch**:     Auto Loader / Copy Activity bulk loads
- **streaming**: Kafka, Event Hubs, Structured Streaming
- **cdc**:       Change Data Capture (Debezium, CDF, MERGE)

Invariants enforced:
- INV-03: Max 3 self-correction attempts
- INV-04: Token budget per task (via TokenTracker)
- INV-06: Audit trail via structured logging

Execution modes:
- **generate_only** (default — no adapter): produces code + artifacts
- **generate_and_execute** (adapter provided): generates code, then
  calls adapter to create resources / execute pipeline on the platform
"""

from __future__ import annotations

from typing import Any

from aadap.agents.adapters.base import PlatformAdapter
from aadap.agents.base import AgentContext, AgentResult, BaseAgent
from aadap.agents.prompts.base import (
    OutputSchemaViolation,
    build_correction_prompt,
    validate_output,
)
from aadap.agents.prompts.ingestion import (
    INGESTION_SCHEMA,
    get_ingestion_prompt,
)
from aadap.agents.token_tracker import TokenBudgetExhaustedError
from aadap.core.logging import get_logger
from aadap.integrations.llm_client import BaseLLMClient

logger = get_logger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

MAX_SELF_CORRECTIONS = 3  # INV-03
DEFAULT_MODEL = "gpt-4o"


# ── IngestionAgent ──────────────────────────────────────────────────────


class IngestionAgent(BaseAgent):
    """
    Data-ingestion code-generation **and execution** agent.

    Generates production-quality ingestion code for batch, streaming,
    or CDC patterns on Databricks or Fabric.  Self-corrects on schema
    violations up to **INV-03** bound.

    When a :class:`PlatformAdapter` is supplied the agent also
    creates the target resources (pipeline / table) on the platform
    and attaches execution results as artefacts.
    """

    def __init__(
        self,
        agent_id: str,
        llm_client: BaseLLMClient,
        model: str = DEFAULT_MODEL,
        platform_adapter: PlatformAdapter | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            agent_type="ingestion",
            **kwargs,
        )
        self._llm_client = llm_client
        self._model = model
        self._platform_adapter = platform_adapter

    # ── Code generation ─────────────────────────────────────────────────

    async def _generate_code(
        self,
        context: AgentContext,
    ) -> tuple[dict[str, Any] | None, int, str | None]:
        """
        Generate ingestion code via LLM with self-correction.

        Returns ``(validated_output, total_tokens, error_or_None)``.
        """
        task_data = context.task_data
        ingestion_type = task_data.get("ingestion_type", "batch")
        prompt_template = get_ingestion_prompt(ingestion_type)

        platform = task_data.get("platform", "databricks")
        prompt = prompt_template.render({
            "task_description": task_data.get("description", ""),
            "platform": platform,
            "source_description": task_data.get("source_description", ""),
            "target_description": task_data.get("target_description", ""),
            "environment": task_data.get("environment", "SANDBOX"),
            "context": task_data.get("context", ""),
        })

        total_tokens = 0

        for attempt in range(1, MAX_SELF_CORRECTIONS + 1):
            logger.info(
                "ingestion_agent.attempt",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                attempt=attempt,
                max_attempts=MAX_SELF_CORRECTIONS,
                ingestion_type=ingestion_type,
                platform=platform,
            )

            try:
                response = await self._llm_client.complete(
                    prompt=prompt,
                    model=self._model,
                )
            except Exception as exc:
                logger.error(
                    "ingestion_agent.llm_error",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    error=str(exc),
                )
                return None, total_tokens, f"ESCALATE: LLM call failed: {exc}"

            # Track tokens (INV-04)
            try:
                self._token_tracker.consume(response.tokens_used)
            except TokenBudgetExhaustedError:
                logger.warning(
                    "ingestion_agent.token_budget_exhausted",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    tokens_used=total_tokens + response.tokens_used,
                )
                return (
                    None,
                    total_tokens + response.tokens_used,
                    "ESCALATE: Token budget exhausted (INV-04)",
                )

            total_tokens += response.tokens_used

            # Validate output
            try:
                validated = validate_output(
                    response.content, INGESTION_SCHEMA,
                )
                logger.info(
                    "ingestion_agent.code_generated",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    attempt=attempt,
                    tokens_used=total_tokens,
                    ingestion_type=ingestion_type,
                )
                return validated, total_tokens, None
            except OutputSchemaViolation as e:
                logger.warning(
                    "ingestion_agent.schema_violation",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    attempt=attempt,
                    errors=e.errors,
                )
                if attempt == MAX_SELF_CORRECTIONS:
                    return (
                        None,
                        total_tokens,
                        (
                            f"ESCALATE: Schema validation failed after "
                            f"{MAX_SELF_CORRECTIONS} attempts (INV-03). "
                            f"Last errors: {e.errors}"
                        ),
                    )
                prompt = build_correction_prompt(
                    prompt, response.content, e,
                )

        return None, total_tokens, "ESCALATE: Unexpected loop exit"  # pragma: no cover

    # ── Platform execution ──────────────────────────────────────────────

    async def _execute_on_platform(
        self,
        context: AgentContext,
        validated: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create resources on the target platform via the adapter.

        Returns a dict describing what was created / executed.
        """
        results: dict[str, Any] = {"actions": []}

        try:
            # 1. Create target table if target config is provided
            target = validated.get("target")
            if target and isinstance(target, dict):
                table_id = await self._platform_adapter.create_table(target)
                results["actions"].append({
                    "action": "create_table",
                    "table_id": table_id,
                })

            # 2. Create an ingestion pipeline from the generated code
            pipeline_def = {
                "name": f"ingestion-{context.task_id}",
                "ingestion_type": validated.get("ingestion_type", "batch"),
                "code": validated.get("code", ""),
                "source": validated.get("source", {}),
                "target": validated.get("target", {}),
            }
            pipeline_id = await self._platform_adapter.create_pipeline(
                pipeline_def,
            )
            results["actions"].append({
                "action": "create_pipeline",
                "pipeline_id": pipeline_id,
            })

            # 3. Execute the pipeline
            execution = await self._platform_adapter.execute_pipeline(
                pipeline_id,
            )
            results["actions"].append({
                "action": "execute_pipeline",
                "pipeline_id": pipeline_id,
                "result": execution,
            })

            results["status"] = "SUCCESS"

        except Exception as exc:
            logger.error(
                "ingestion_agent.execution_error",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                error=str(exc),
            )
            results["status"] = "FAILED"
            results["error"] = str(exc)

        return results

    # ── Main entry-point ────────────────────────────────────────────────

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        """
        Generate ingestion code — and optionally execute on the platform.

        Phase 1: Generate + validate code (self-correction up to INV-03).
        Phase 2: If a ``platform_adapter`` is configured, create
                 resources and execute the ingestion pipeline.
        """
        # ── Phase 1: Code generation ────────────────────────────────────
        validated, total_tokens, gen_error = await self._generate_code(
            context,
        )

        if gen_error is not None:
            return AgentResult(
                success=False,
                error=gen_error,
                tokens_used=total_tokens,
            )

        artifacts: list[dict[str, Any]] = [
            {
                "type": "generated_code",
                "ingestion_type": validated.get("ingestion_type", "batch"),
                "platform": validated.get("platform", "unknown"),
                "content": validated,
            },
        ]

        # ── Phase 2: Platform execution (optional) ─────────────────────
        execution_output: dict[str, Any] | None = None

        if self._platform_adapter is not None:
            execution_output = await self._execute_on_platform(
                context, validated,
            )
            artifacts.append({
                "type": "execution_result",
                "platform": validated.get("platform", "unknown"),
                "status": execution_output.get("status"),
                "actions": execution_output.get("actions", []),
                "error": execution_output.get("error"),
            })

            # If execution failed, still return all artefacts but mark failure
            if execution_output.get("status") == "FAILED":
                logger.warning(
                    "ingestion_agent.execution_failed",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    error=execution_output.get("error"),
                )
                return AgentResult(
                    success=False,
                    error=(
                        f"Platform execution failed: "
                        f"{execution_output.get('error')}"
                    ),
                    output={
                        "generated_code": validated,
                        "execution": execution_output,
                    },
                    tokens_used=total_tokens,
                    artifacts=artifacts,
                )

        # ── Build final output ──────────────────────────────────────────
        output: dict[str, Any] = {**validated}
        if execution_output is not None:
            output["execution"] = execution_output

        logger.info(
            "ingestion_agent.success",
            agent_id=self._agent_id,
            task_id=str(context.task_id),
            tokens_used=total_tokens,
            ingestion_type=validated.get("ingestion_type"),
            platform=validated.get("platform"),
            executed=execution_output is not None,
        )

        return AgentResult(
            success=True,
            output=output,
            tokens_used=total_tokens,
            artifacts=artifacts,
        )
