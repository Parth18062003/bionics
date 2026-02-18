"""
AADAP — Fabric Agent (Microsoft Fabric Python / Scala / SQL)
================================================================
Code-generation **and execution** agent for Microsoft Fabric workloads.

Architecture layer: L4 (Agent Layer).
Mirrors DeveloperAgent pattern but targets Fabric platform.

Invariants enforced:
- INV-03: Max 3 self-correction attempts
- INV-04: Token budget per task (via TokenTracker)
- INV-05: Sandbox isolation via FabricClient environment validation
- INV-06: Audit trail via structured logging

Supports:
- Python/PySpark notebooks on Fabric Spark
- Scala/Spark notebooks on Fabric
- SQL queries on Fabric Lakehouse SQL endpoint / Warehouse

Execution modes:
- **generate_only** (default when no fabric_client): produces code + artifacts
- **generate_and_execute** (when fabric_client is provided): generates code,
  submits to Fabric, polls for completion, returns both code and execution results
"""

from __future__ import annotations

from typing import Any

from aadap.agents.base import AgentContext, AgentResult, BaseAgent
from aadap.agents.prompts.base import (
    OutputSchemaViolation,
    build_correction_prompt,
    validate_output,
)
from aadap.agents.prompts.fabric import (
    FABRIC_CODE_SCHEMA,
    get_fabric_prompt,
)
from aadap.agents.token_tracker import TokenBudgetExhaustedError
from aadap.core.logging import get_logger
from aadap.integrations.fabric_client import (
    BaseFabricClient,
    JobStatus as FabricJobStatus,
)
from aadap.integrations.llm_client import BaseLLMClient

logger = get_logger(__name__)

# ── Constants ───────────────────────────────────────────────────────────

MAX_SELF_CORRECTIONS = 3  # INV-03
DEFAULT_MODEL = "gpt-4o"
MAX_POLL_ATTEMPTS = 120       # ~10 minutes at 5 s interval
POLL_INTERVAL_SECONDS = 5.0


# ── FabricAgent ─────────────────────────────────────────────────────────


class FabricAgent(BaseAgent):
    """
    Microsoft Fabric code-generation **and execution** agent.

    Generates production-quality Python, Scala, or SQL code for
    Fabric notebooks and SQL endpoints.  Self-corrects on schema
    violations up to INV-03 bound.

    When a :class:`BaseFabricClient` is supplied the agent also:
    1. Submits the generated code to Fabric.
    2. Polls until the job reaches a terminal state.
    3. Retrieves the output and attaches it as an ``execution_result``
       artifact alongside the ``generated_code`` artifact.
    """

    def __init__(
        self,
        agent_id: str,
        llm_client: BaseLLMClient,
        model: str = DEFAULT_MODEL,
        default_language: str = "python",
        fabric_client: BaseFabricClient | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            agent_type="fabric",
            **kwargs,
        )
        self._llm_client = llm_client
        self._model = model
        self._default_language = default_language
        self._fabric_client = fabric_client

    # ── Code generation ─────────────────────────────────────────────────

    async def _generate_code(
        self, context: AgentContext, language: str,
    ) -> tuple[dict[str, Any] | None, int, str | None]:
        """
        Generate code via LLM with self-correction.

        Returns (validated_output_dict, total_tokens, error_string_or_None).
        """
        task_data = context.task_data
        prompt_template = get_fabric_prompt(language)
        prompt = prompt_template.render({
            "task_description": task_data.get("description", ""),
            "environment": task_data.get("environment", "SANDBOX"),
            "context": task_data.get("context", "Microsoft Fabric Lakehouse"),
        })

        total_tokens = 0

        for attempt in range(1, MAX_SELF_CORRECTIONS + 1):
            logger.info(
                "fabric_agent.attempt",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                attempt=attempt,
                max_attempts=MAX_SELF_CORRECTIONS,
                language=language,
            )

            try:
                response = await self._llm_client.complete(
                    prompt=prompt,
                    model=self._model,
                )
            except Exception as exc:
                logger.error(
                    "fabric_agent.llm_error",
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
                    "fabric_agent.token_budget_exhausted",
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
                    response.content, FABRIC_CODE_SCHEMA,
                )
                logger.info(
                    "fabric_agent.code_generated",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    attempt=attempt,
                    tokens_used=total_tokens,
                    language=language,
                )
                return validated, total_tokens, None
            except OutputSchemaViolation as e:
                logger.warning(
                    "fabric_agent.schema_violation",
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

        return None, total_tokens, "ESCALATE: Unexpected loop exit"

    # ── Fabric execution ────────────────────────────────────────────────

    async def _submit_and_poll(
        self,
        context: AgentContext,
        code: str,
        language: str,
    ) -> dict[str, Any]:
        """
        Submit *code* to Fabric, poll to completion and retrieve output.

        Returns a dict with keys: status, output, error, job_id, duration_ms.
        """
        import asyncio

        environment = context.task_data.get("environment", "SANDBOX")

        try:
            submission = await self._fabric_client.submit_job(
                task_id=context.task_id,
                code=code,
                environment=environment,
                language=language,
            )

            logger.info(
                "fabric_agent.job_submitted",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                job_id=submission.job_id,
            )

            # Poll until terminal state
            for _ in range(MAX_POLL_ATTEMPTS):
                status = await self._fabric_client.get_job_status(
                    submission.job_id,
                )
                if status in (
                    FabricJobStatus.SUCCESS,
                    FabricJobStatus.FAILED,
                    FabricJobStatus.CANCELLED,
                ):
                    break
                await asyncio.sleep(POLL_INTERVAL_SECONDS)

            # Retrieve output
            job_result = await self._fabric_client.get_job_output(
                submission.job_id,
            )

            logger.info(
                "fabric_agent.job_completed",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                job_id=submission.job_id,
                status=job_result.status.value,
                duration_ms=job_result.duration_ms,
            )

            return {
                "status": job_result.status.value,
                "output": job_result.output,
                "error": job_result.error,
                "job_id": submission.job_id,
                "duration_ms": job_result.duration_ms,
                "metadata": job_result.metadata,
            }

        except Exception as exc:
            logger.error(
                "fabric_agent.execution_error",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                error=str(exc),
            )
            return {
                "status": "FAILED",
                "output": None,
                "error": str(exc),
                "job_id": None,
                "duration_ms": None,
                "metadata": {},
            }

    # ── Main entry-point ────────────────────────────────────────────────

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        """
        Generate Fabric code — and optionally execute it on Fabric.

        Phase 1: Generate + validate code (self-correction up to INV-03).
        Phase 2: If a ``fabric_client`` is configured, submit the code
                 to Fabric, poll for completion, and return execution output
                 alongside the generated code artifacts.
        """
        task_data = context.task_data
        language = task_data.get("language", self._default_language)

        # ── Phase 1: Code generation ────────────────────────────────────
        validated, total_tokens, gen_error = await self._generate_code(
            context, language,
        )

        if gen_error is not None:
            return AgentResult(
                success=False,
                error=gen_error,
                tokens_used=total_tokens,
            )

        code_text = validated["code"]
        artifacts: list[dict[str, Any]] = [
            {
                "type": "generated_code",
                "language": validated.get("language", language),
                "platform": "Microsoft Fabric",
                "content": validated,
            },
        ]

        # ── Phase 2: Fabric execution (optional) ───────────────────────
        execution_output: dict[str, Any] | None = None

        if self._fabric_client is not None:
            execution_output = await self._submit_and_poll(
                context, code_text, language,
            )
            artifacts.append({
                "type": "execution_result",
                "platform": "Microsoft Fabric",
                "job_id": execution_output.get("job_id"),
                "status": execution_output.get("status"),
                "output": execution_output.get("output"),
                "error": execution_output.get("error"),
                "duration_ms": execution_output.get("duration_ms"),
            })

            # If execution failed, still return all artifacts but mark failure
            if execution_output.get("status") == "FAILED":
                logger.warning(
                    "fabric_agent.execution_failed",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    error=execution_output.get("error"),
                )
                return AgentResult(
                    success=False,
                    error=f"Fabric execution failed: {execution_output.get('error')}",
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
            "fabric_agent.success",
            agent_id=self._agent_id,
            task_id=str(context.task_id),
            tokens_used=total_tokens,
            language=language,
            executed=execution_output is not None,
        )

        return AgentResult(
            success=True,
            output=output,
            tokens_used=total_tokens,
            artifacts=artifacts,
        )
