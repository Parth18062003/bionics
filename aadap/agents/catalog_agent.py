"""
AADAP — Catalog Agent
=========================
Code-generation and execution agent for catalog/schema/lakehouse resource
management on Azure Databricks and Microsoft Fabric.

Architecture layer: L4 (Agent Layer).
Follows IngestionAgent / ETLPipelineAgent / JobSchedulerAgent conventions.

Supports two catalog modes via dedicated prompt templates:
- **schema_design**: Create/alter resource definitions
- **permission_grant**: Generate grants and permission payloads

Invariants enforced:
- INV-03: Max 3 self-correction attempts
- INV-04: Token budget per task (via TokenTracker)
- INV-06: Audit trail via structured logging
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
from aadap.agents.prompts.catalog import CATALOG_SCHEMA, get_catalog_prompt
from aadap.agents.token_tracker import TokenBudgetExhaustedError
from aadap.core.logging import get_logger
from aadap.integrations.llm_client import BaseLLMClient

logger = get_logger(__name__)

MAX_SELF_CORRECTIONS = 3  # INV-03
DEFAULT_MODEL = "gpt-4o"
_APPROVAL_REQUIRED_OPERATIONS = {"grant", "drop"}


class CatalogAgent(BaseAgent):
    """Catalog governance and schema-management agent."""

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
            agent_type="catalog",
            **kwargs,
        )
        self._llm_client = llm_client
        self._model = model
        self._platform_adapter = platform_adapter

    def _has_permission_approval(self, context: AgentContext) -> bool:
        """Return True if the task includes explicit approval metadata."""
        return bool(
            context.task_data.get("approval_granted", False)
            or context.metadata.get("approval_granted", False)
        )

    async def _generate_code(
        self,
        context: AgentContext,
    ) -> tuple[dict[str, Any] | None, int, str | None]:
        """Generate catalog statements via LLM with self-correction."""
        task_data = context.task_data
        catalog_mode = task_data.get("catalog_mode", "schema_design")
        prompt_template = get_catalog_prompt(catalog_mode)

        platform = task_data.get("platform", "databricks")
        prompt = prompt_template.render({
            "task_description": task_data.get("description", ""),
            "platform": platform,
            "operation": task_data.get("operation", "create"),
            "resource_type": task_data.get("resource_type", "schema"),
            "naming_conventions": task_data.get("naming_conventions", ""),
            "principals": task_data.get("principals", ""),
            "required_access": task_data.get("required_access", ""),
            "environment": task_data.get("environment", "SANDBOX"),
            "context": task_data.get("context", ""),
        })

        total_tokens = 0

        for attempt in range(1, MAX_SELF_CORRECTIONS + 1):
            logger.info(
                "catalog_agent.attempt",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                attempt=attempt,
                max_attempts=MAX_SELF_CORRECTIONS,
                catalog_mode=catalog_mode,
                platform=platform,
            )

            try:
                response = await self._llm_client.complete(
                    prompt=prompt,
                    model=self._model,
                )
            except Exception as exc:
                logger.error(
                    "catalog_agent.llm_error",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    error=str(exc),
                )
                return None, total_tokens, f"ESCALATE: LLM call failed: {exc}"

            assert self._token_tracker is not None
            try:
                self._token_tracker.consume(response.tokens_used)
            except TokenBudgetExhaustedError:
                logger.warning(
                    "catalog_agent.token_budget_exhausted",
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

            try:
                validated = validate_output(response.content, CATALOG_SCHEMA)
                logger.info(
                    "catalog_agent.code_generated",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    attempt=attempt,
                    tokens_used=total_tokens,
                    operation=validated.get("operation"),
                    resource_type=validated.get("resource_type"),
                )
                return validated, total_tokens, None
            except OutputSchemaViolation as error:
                logger.warning(
                    "catalog_agent.schema_violation",
                    agent_id=self._agent_id,
                    task_id=str(context.task_id),
                    attempt=attempt,
                    errors=error.errors,
                )
                if attempt == MAX_SELF_CORRECTIONS:
                    return (
                        None,
                        total_tokens,
                        (
                            f"ESCALATE: Schema validation failed after "
                            f"{MAX_SELF_CORRECTIONS} attempts (INV-03). "
                            f"Last errors: {error.errors}"
                        ),
                    )
                prompt = build_correction_prompt(
                    prompt, response.content, error)

        return None, total_tokens, "ESCALATE: Unexpected loop exit"  # pragma: no cover

    async def _execute_on_platform(
        self,
        context: AgentContext,
        validated: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute DDL/DCL statements on the target platform."""
        results: dict[str, Any] = {"actions": []}

        assert self._platform_adapter is not None

        operation = str(validated.get("operation", "create")).lower()
        if operation in _APPROVAL_REQUIRED_OPERATIONS and not self._has_permission_approval(context):
            results["status"] = "FAILED"
            results["error"] = (
                "Approval required for permission-sensitive operations "
                "(grant/drop)."
            )
            return results

        try:
            ddl_statements = validated.get("ddl_statements") or []
            for statement in ddl_statements:
                execution = await self._platform_adapter.execute_sql(statement)
                results["actions"].append({
                    "action": "execute_sql",
                    "statement": statement,
                    "result": execution,
                })

            api_payloads = validated.get("api_payloads") or []
            for payload in api_payloads:
                resource_type = str(validated.get("resource_type", "")).lower()
                if resource_type in {"table", "schema"}:
                    resource_id = await self._platform_adapter.create_table(payload)
                    results["actions"].append({
                        "action": "create_table",
                        "resource_id": resource_id,
                    })
                elif resource_type in {"lakehouse", "volume"}:
                    resource_id = await self._platform_adapter.create_shortcut(payload)
                    results["actions"].append({
                        "action": "create_shortcut",
                        "resource_id": resource_id,
                    })

            results["status"] = "SUCCESS"
            results["executed_statements"] = len(ddl_statements)
        except Exception as exc:
            logger.error(
                "catalog_agent.execution_error",
                agent_id=self._agent_id,
                task_id=str(context.task_id),
                error=str(exc),
            )
            results["status"] = "FAILED"
            results["error"] = str(exc)

        return results

    async def _do_execute(self, context: AgentContext) -> AgentResult:
        """Generate catalog output and optionally execute on platform."""
        validated, total_tokens, generation_error = await self._generate_code(context)

        if generation_error is not None:
            return AgentResult(
                success=False,
                error=generation_error,
                tokens_used=total_tokens,
            )

        assert validated is not None

        artifacts: list[dict[str, Any]] = [
            {
                "type": "generated_code",
                "operation": validated.get("operation", "create"),
                "resource_type": validated.get("resource_type", "schema"),
                "platform": validated.get("platform", "unknown"),
                "content": validated,
            },
        ]

        execution_output: dict[str, Any] | None = None

        if self._platform_adapter is not None:
            execution_output = await self._execute_on_platform(context, validated)
            artifacts.append({
                "type": "execution_result",
                "platform": validated.get("platform", "unknown"),
                "status": execution_output.get("status"),
                "actions": execution_output.get("actions", []),
                "error": execution_output.get("error"),
                "executed_statements": execution_output.get("executed_statements", 0),
            })

            if execution_output.get("status") == "FAILED":
                return AgentResult(
                    success=False,
                    error=(
                        "Platform execution failed: "
                        f"{execution_output.get('error')}"
                    ),
                    output={
                        "generated_code": validated,
                        "execution": execution_output,
                    },
                    tokens_used=total_tokens,
                    artifacts=artifacts,
                )

        output: dict[str, Any] = {**validated}
        if execution_output is not None:
            output["execution"] = execution_output

        return AgentResult(
            success=True,
            output=output,
            tokens_used=total_tokens,
            artifacts=artifacts,
        )
