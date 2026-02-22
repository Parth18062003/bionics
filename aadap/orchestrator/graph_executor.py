"""
AADAP — Graph Executor
=========================
Handles execution logic for LangGraph nodes.

This module provides:
- Direct execution (list/preview operations)
- Platform execution (Databricks/Fabric)
- Approval flow handling
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from aadap.agents.base import AgentContext, AgentResult
from aadap.core.exceptions import (
    AADAPError,
    AgentLifecycleError,
    ExecutionError,
    IntegrationError,
    OrchestratorError,
)
from aadap.core.logging import get_logger
from aadap.core.task_types import TaskMode, OperationType, is_direct_execution
from aadap.orchestrator.dispatcher import AgentDispatcher
from aadap.orchestrator.routing import RoutingDecision, TaskRouter
from aadap.safety.static_analysis import StaticAnalyzer

logger = get_logger(__name__)


class GraphExecutor:
    """Handles execution logic for LangGraph nodes."""

    def __init__(
        self,
        dispatcher: AgentDispatcher,
        router: TaskRouter,
    ) -> None:
        self._dispatcher = dispatcher
        self._router = router
        self._analyzer = StaticAnalyzer()

    def _detect_task_mode(self, metadata: dict[str, Any]) -> TaskMode | None:
        """Detect task mode from metadata."""
        task_mode = metadata.get("task_mode")
        if task_mode:
            try:
                return TaskMode(task_mode)
            except ValueError:
                pass
        return None

    def _detect_operation_type(self, metadata: dict[str, Any]) -> OperationType | None:
        """Detect operation type from metadata."""
        op_type = metadata.get("operation_type")
        if op_type:
            try:
                return OperationType(op_type)
            except ValueError:
                pass
        return None

    def is_direct_execution(self, metadata: dict[str, Any]) -> bool:
        """Check if task should execute directly without code generation."""
        task_mode = self._detect_task_mode(metadata)
        operation_type = self._detect_operation_type(metadata)
        return is_direct_execution(task_mode, operation_type)

    async def execute_routing(
        self,
        task_id: uuid.UUID,
        metadata: dict[str, Any],
    ) -> RoutingDecision | None:
        """Execute routing decision for task."""
        try:
            decision = self._router.route(
                task_id=task_id,
                title=metadata.get("title", ""),
                description=metadata.get("description", ""),
                metadata=metadata,
                environment=metadata.get("environment", "SANDBOX"),
            )
            logger.info(
                "executor.routing_complete",
                task_id=str(task_id),
                agent_type=decision.agent_type,
                confidence=decision.confidence,
            )
            return decision
        except OrchestratorError as exc:
            logger.error(
                "executor.routing_failed",
                task_id=str(task_id),
                error_code=exc.error_code,
                severity=exc.severity.value,
                error=str(exc),
            )
            return RoutingDecision(
                agent_type="developer",
                confidence=0.0,
                routing_method="fallback",
                reasoning=f"Routing failed: {exc}",
            )

    async def execute_direct_operation(
        self,
        task_id: uuid.UUID,
        metadata: dict[str, Any],
    ) -> AgentResult:
        """Execute a direct operation (list/preview) without code generation."""
        from aadap.services.databricks_explorer import DatabricksExplorerService
        from aadap.services.fabric_explorer import FabricExplorerService
        from aadap.integrations.databricks_client import DatabricksClient
        from aadap.integrations.fabric_client import FabricClient

        operation_type = self._detect_operation_type(metadata)
        platform = metadata.get("platform", "databricks")
        catalog = metadata.get("catalog")
        schema_name = metadata.get("schema_name")
        table = metadata.get("table")

        result_data: dict[str, Any] = {}

        try:
            if platform == "fabric":
                fabric = FabricClient.from_settings()
                explorer = FabricExplorerService(fabric)
            else:
                dbx = DatabricksClient.from_settings()
                explorer = DatabricksExplorerService(dbx)

            if operation_type == OperationType.LIST_TABLES and catalog and schema_name:
                tables = await explorer.list_tables(catalog, schema_name)
                result_data = {
                    "tables": [
                        {
                            "id": t.id,
                            "name": t.name,
                            "schema": t.schema_name,
                            "catalog": t.catalog_name,
                            "full_name": t.full_name,
                            "type": t.type,
                        }
                        for t in tables
                    ]
                }
            elif operation_type == OperationType.LIST_CATALOGS:
                catalogs = await explorer.list_catalogs()
                result_data = {
                    "catalogs": [
                        {"id": c.id, "name": c.name, "type": c.type}
                        for c in catalogs
                    ]
                }
            elif operation_type == OperationType.PREVIEW_TABLE and catalog and schema_name and table:
                preview = await explorer.preview_table(catalog, schema_name, table)
                if preview:
                    result_data = {
                        "columns": preview.columns,
                        "rows": preview.rows,
                        "row_count": preview.row_count,
                    }
            elif operation_type == OperationType.GET_SCHEMA and catalog and schema_name and table:
                detail = await explorer.get_table_schema(catalog, schema_name, table)
                if detail:
                    result_data = {
                        "table": detail.name,
                        "columns": [
                            {
                                "name": c.name,
                                "data_type": c.data_type,
                                "nullable": c.nullable,
                            }
                            for c in detail.columns
                        ],
                    }
            else:
                result_data = {
                    "message": f"Direct execution for {operation_type} completed",
                    "catalog": catalog,
                    "schema": schema_name,
                    "table": table,
                }

            logger.info(
                "executor.direct_complete",
                task_id=str(task_id),
                operation_type=operation_type.value if operation_type else None,
            )

            return AgentResult(
                success=True,
                output=result_data,
                artifacts=[{
                    "type": "direct_execution_result",
                    "content": result_data,
                }],
            )

        except (IntegrationError, ExecutionError) as exc:
            logger.error(
                "executor.direct_failed",
                task_id=str(task_id),
                error_code=exc.error_code,
                severity=exc.severity.value,
                error=str(exc),
            )
            return AgentResult(
                success=False,
                error=str(exc),
            )

    async def execute_development(
        self,
        task_id: uuid.UUID,
        metadata: dict[str, Any],
        routing_decision: dict[str, Any] | None,
    ) -> AgentResult:
        """Execute development agent for code generation."""
        try:
            agent_type = "developer"
            if routing_decision:
                agent_type = routing_decision.get("agent_type", "developer")

            context = AgentContext(
                task_id=task_id,
                task_data={
                    "title": metadata.get("title", ""),
                    "description": metadata.get("description", ""),
                    "environment": metadata.get("environment", "SANDBOX"),
                    "platform": metadata.get("platform", "databricks"),
                },
                token_budget=metadata.get("token_budget", 50_000),
                allowed_tools=set(),
                metadata=metadata,
            )

            return await self._dispatcher.dispatch_and_execute(
                agent_type=agent_type,
                context=context,
            )
        except (AgentLifecycleError, ExecutionError) as exc:
            logger.error(
                "executor.development_failed",
                task_id=str(task_id),
                error_code=exc.error_code,
                severity=exc.severity.value,
                error=str(exc),
            )
            return AgentResult(success=False, error=str(exc))

    async def execute_validation(
        self,
        task_id: uuid.UUID,
        code: str,
        metadata: dict[str, Any],
    ) -> AgentResult:
        """Execute validation agent."""
        try:
            language = metadata.get("language", "python")

            result = self._analyzer.evaluate(code, language=language)

            is_valid = result.passed
            findings = [
                {
                    "line": f.line,
                    "pattern": f.pattern,
                    "description": f.description,
                    "severity": f.severity.value,
                }
                for f in result.findings
            ]

            context = AgentContext(
                task_id=task_id,
                task_data={
                    "code": code,
                    "language": language,
                    "description": metadata.get("description", ""),
                    "environment": metadata.get("environment", "SANDBOX"),
                },
                token_budget=metadata.get("token_budget", 50_000),
                allowed_tools=set(),
            )

            llm_result = await self._dispatcher.dispatch_and_execute(
                agent_type="validation",
                context=context,
            )

            if llm_result.success and llm_result.output:
                llm_output = llm_result.output
                merged = {
                    "is_valid": is_valid and llm_output.get("is_valid", True),
                    "risk_score": max(
                        llm_output.get("risk_score", 0),
                        self._risk_level_to_score(result.risk_level.value),
                    ),
                    "issues": findings + llm_output.get("issues", []),
                    "recommendation": llm_output.get("recommendation", "approve"),
                    "safety_pipeline": {
                        "risk_level": result.risk_level.value,
                        "passed": result.passed,
                        "findings": findings,
                    },
                }
                return AgentResult(
                    success=is_valid,
                    output=merged,
                    artifacts=[{
                        "type": "validation_report",
                        "content": merged,
                    }],
                )

            return AgentResult(
                success=is_valid,
                output={
                    "is_valid": is_valid,
                    "risk_level": result.risk_level.value,
                    "findings": findings,
                },
            )

        except ExecutionError as exc:
            logger.error(
                "executor.validation_failed",
                task_id=str(task_id),
                error_code=exc.error_code,
                severity=exc.severity.value,
                error=str(exc),
            )
            return AgentResult(success=False, error=str(exc))

    def _risk_level_to_score(self, risk_level: str) -> float:
        """Convert risk level string to numeric score."""
        mapping = {
            "NONE": 0.0,
            "LOW": 0.25,
            "MEDIUM": 0.5,
            "HIGH": 0.75,
            "CRITICAL": 1.0,
        }
        return mapping.get(risk_level, 0.0)

    async def execute_optimization(
        self,
        task_id: uuid.UUID,
        code: str,
        metadata: dict[str, Any],
    ) -> AgentResult:
        """Execute optimization agent."""
        try:
            context = AgentContext(
                task_id=task_id,
                task_data={
                    "code": code,
                    "platform": metadata.get("platform", "databricks"),
                    "environment": metadata.get("environment", "SANDBOX"),
                },
                token_budget=metadata.get("token_budget", 50_000),
                allowed_tools=set(),
            )

            return await self._dispatcher.dispatch_and_execute(
                agent_type="optimization",
                context=context,
            )
        except ExecutionError as exc:
            logger.error(
                "executor.optimization_failed",
                task_id=str(task_id),
                error_code=exc.error_code,
                severity=exc.severity.value,
                error=str(exc),
            )
            return AgentResult(success=False, error=str(exc))

    async def execute_on_platform(
        self,
        task_id: uuid.UUID,
        code: str,
        metadata: dict[str, Any],
    ) -> AgentResult:
        """Execute code on platform (Databricks or Fabric)."""
        from aadap.integrations.databricks_client import DatabricksClient
        from aadap.integrations.fabric_client import FabricClient

        platform = metadata.get("platform", "databricks")
        environment = metadata.get("environment", "SANDBOX")
        language = metadata.get("language", "python")

        try:
            if platform == "fabric":
                fabric = FabricClient.from_settings()
                submission = await fabric.submit_job(
                    task_id=task_id,
                    code=code,
                    environment=environment,
                    language=language,
                )
                status = await fabric.get_job_status(submission.job_id)
                output = await fabric.get_job_output(submission.job_id)
            else:
                dbx = DatabricksClient.from_settings()
                submission = await dbx.submit_job(
                    task_id=task_id,
                    code=code,
                    environment=environment,
                    language=language,
                )
                status = await dbx.get_job_status(submission.job_id)
                output = await dbx.get_job_output(submission.job_id)

            success = output.status.value == "SUCCESS"

            logger.info(
                "executor.platform_complete",
                task_id=str(task_id),
                platform=platform,
                success=success,
                job_id=submission.job_id,
            )

            return AgentResult(
                success=success,
                output={
                    "job_id": submission.job_id,
                    "status": status.status.value,
                    "output": output.output,
                    "duration_ms": output.duration_ms,
                },
                error=output.error if not success else None,
            )

        except IntegrationError as exc:
            logger.error(
                "executor.platform_failed",
                task_id=str(task_id),
                platform=platform,
                error_code=exc.error_code,
                severity=exc.severity.value,
                error=str(exc),
            )
            return AgentResult(success=False, error=str(exc))

    async def request_approval(
        self,
        task_id: uuid.UUID,
        code: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Request approval for the task."""
        from aadap.safety.approval_engine import get_approval_engine, OperationRequest

        environment = metadata.get("environment", "SANDBOX")
        platform = metadata.get("platform", "databricks")
        language = metadata.get("language", "python")

        operation_type = self._classify_operation_type(code, environment)

        engine = get_approval_engine()
        approval_record = await engine.request_approval_async(
            OperationRequest(
                task_id=task_id,
                operation_type=operation_type,
                environment=environment,
                code=code,
                requested_by="langgraph_executor",
                metadata={
                    "platform": platform,
                    "language": language,
                },
            ),
        )

        return {
            "approval_id": str(approval_record.id),
            "status": approval_record.status.value,
            "requires_approval": approval_record.status.value == "PENDING",
            "operation_type": operation_type,
        }

    def _classify_operation_type(
        self,
        code: str,
        environment: str,
    ) -> str:
        """Classify operation type for approval policy."""
        lowered = code.lower()
        destructive_tokens = ["drop ", "truncate ", "delete ", "revoke "]
        if any(token in lowered for token in destructive_tokens):
            return "destructive"
        if environment.upper() == "PRODUCTION":
            return "write"
        return "read_only"
