"""
AADAP — Job Scheduler Agent
===============================
Code-generation **and execution** agent for job scheduling and
orchestration on Azure Databricks and Microsoft Fabric.

Architecture layer: L4 (Agent Layer).
Follows IngestionAgent / ETLPipelineAgent conventions.

Supports three scheduler modes via dedicated prompt templates:
- **job_creation**: Multi-task job / workflow definitions
- **schedule**:     Cron expressions, event triggers, retry policies
- **dag**:          Task dependency graph construction

Invariants enforced:
- INV-03: Max 3 self-correction attempts
- INV-04: Token budget per task (via TokenTracker)
- INV-06: Audit trail via structured logging

Execution modes:
- **generate_only** (default — no adapter): produces job definition artefacts
- **generate_and_execute** (adapter provided): generates definition, then
  creates the job on the platform and returns the job ID
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
from aadap.agents.prompts.job_scheduler import (
    JOB_SCHEDULER_SCHEMA,
    get_job_scheduler_prompt,
)
from aadap.agents.token_tracker import TokenBudgetExhaustedError
from aadap.core.logging import get_logger
from aadap.integrations.llm_client import BaseLLMClient

logger = get_logger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

MAX_SELF_CORRECTIONS = 3  # INV-03
DEFAULT_MODEL = "gpt-4o"


# ── JobSchedulerAgent ──────────────────────────────────────────────────


class JobSchedulerAgent(BaseAgent):
    """
    Job scheduling and orchestration agent.

    Generates multi-task job definitions, cron schedules, event triggers,
    and task DAGs for Databricks or Fabric.  Self-corrects on schema
    violations up to **INV-03** bound.

    When a :class:`PlatformAdapter` is supplied the agent also creates
    the job on the platform and returns the job ID for monitoring.
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
            agent_type="job_scheduler",
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
        Generate job definition via LLM with self-correction.

        Returns ``(validated_output, total_tokens, error_or_None)``.
        """
        task_data = context.task_data
        scheduler_mode = task_data.get("scheduler_mode", "job_creation")
        prompt_template = get_job_scheduler_prompt(scheduler_mode)

        platform = task_data.get("platform", "databricks")
        prompt = prompt_template.render({
            "task_description": task_data.get("description", ""),
            "platform": platform,
            "job_type": task_data.get("job_type", "notebook"),
            "tasks_description": task_data.get("tasks_description", ""),
            "freshness": task_data.get("freshness", "daily"),
            "dependencies": task_data.get("dependencies", ""),
            "environment": task_data.get("environment", "SANDBOX"),
            "context": task_data.get("context", ""),
        })

        total_tokens = 0

        for attempt in range(1, MAX_SELF_CORRECTIONS + 1):
            logger.info(
                "job_scheduler_agent.attempt",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                attempt=attempt,
                max_attempts=MAX_SELF_CORRECTIONS,
                scheduler_mode=scheduler_mode,
                platform=platform,
            )

            try:
                response = await self._llm_client.complete(
                    prompt=prompt,
                    model=self._model,
                )
            except Exception as exc:
                logger.error(
                    "job_scheduler_agent.llm_error",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    error=str(exc),
                )
                return None, total_tokens, f"ESCALATE: LLM call failed: {exc}"

            # Track tokens (INV-04)
            assert self._token_tracker is not None  # set by accept_task
            try:
                self._token_tracker.consume(response.tokens_used)
            except TokenBudgetExhaustedError:
                logger.warning(
                    "job_scheduler_agent.token_budget_exhausted",
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
                    response.content, JOB_SCHEDULER_SCHEMA,
                )
                logger.info(
                    "job_scheduler_agent.code_generated",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    attempt=attempt,
                    tokens_used=total_tokens,
                    scheduler_mode=scheduler_mode,
                )
                return validated, total_tokens, None
            except OutputSchemaViolation as e:
                logger.warning(
                    "job_scheduler_agent.schema_violation",
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
        Create and optionally execute the job on the target platform.

        Returns a dict describing what was created / executed.
        """
        results: dict[str, Any] = {"actions": []}

        assert self._platform_adapter is not None  # caller guards

        try:
            job_def = validated.get("job_definition", {})
            job_def.setdefault("name", f"scheduled-job-{context.task_id}")

            # 1. Create the job
            job_id = await self._platform_adapter.create_job(job_def)
            results["actions"].append({
                "action": "create_job",
                "job_id": job_id,
            })
            results["job_id"] = job_id

            # 2. Execute the job if task_data requests immediate run
            if context.task_data.get("run_immediately", False):
                execution = await self._platform_adapter.execute_job(
                    job_id,
                    params=context.task_data.get("run_params"),
                )
                results["actions"].append({
                    "action": "execute_job",
                    "job_id": job_id,
                    "result": execution,
                })

            results["status"] = "SUCCESS"
            results["created"] = True

        except Exception as exc:
            logger.error(
                "job_scheduler_agent.execution_error",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                error=str(exc),
            )
            results["status"] = "FAILED"
            results["error"] = str(exc)
            results["created"] = False

        return results

    # ── Main entry-point ────────────────────────────────────────────────

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        """
        Generate job definition — and optionally create on the platform.

        Phase 1: Generate + validate definition (self-correction up to INV-03).
        Phase 2: If a ``platform_adapter`` is configured, create the job
                 and optionally trigger an immediate run.
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

        assert validated is not None  # guaranteed when gen_error is None

        artifacts: list[dict[str, Any]] = [
            {
                "type": "generated_code",
                "job_type": validated.get("job_type", "notebook"),
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
                "job_id": execution_output.get("job_id"),
                "actions": execution_output.get("actions", []),
                "error": execution_output.get("error"),
                "created": execution_output.get("created", False),
            })

            if execution_output.get("status") == "FAILED":
                logger.warning(
                    "job_scheduler_agent.execution_failed",
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
            "job_scheduler_agent.success",
            agent_id=self._agent_id,
            task_id=str(context.task_id),
            tokens_used=total_tokens,
            job_type=validated.get("job_type"),
            platform=validated.get("platform"),
            executed=execution_output is not None,
        )

        return AgentResult(
            success=True,
            output=output,
            tokens_used=total_tokens,
            artifacts=artifacts,
        )
