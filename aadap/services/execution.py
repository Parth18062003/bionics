"""
AADAP — End-to-End Task Execution Service
=============================================
Orchestrates the full lifecycle of a submitted task:

    SUBMITTED → PARSING → PARSED → PLANNING → PLANNED
    → AGENT_ASSIGNMENT → AGENT_ASSIGNED → IN_DEVELOPMENT
    → CODE_GENERATED → IN_VALIDATION → VALIDATION_PASSED
    → DEPLOYING → DEPLOYED → COMPLETED

Architecture layer: L5 (Orchestration) — binds L4 agents, L3 integrations,
and L2 memory into the authoritative 25-state pipeline.

Invariants enforced:
- INV-01: Approval gates for destructive / production ops
- INV-02: All transitions persisted before acknowledgment
- INV-03: Max 3 self-corrections
- INV-04: Token budget (50k default)
- INV-05: Sandbox isolation via Databricks client
- INV-06: Full audit trail
- INV-07: Validation before deployment

Usage (from API route or background worker):
    service = ExecutionService.create()
    result  = await service.execute_task(task_id)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from aadap.agents import (
    CatalogAgent,
    ETLPipelineAgent,
    IngestionAgent,
    JobSchedulerAgent,
)
from aadap.agents.adapters import DatabricksAdapter, FabricAdapter, PlatformAdapter
from aadap.agents.base import AgentContext, BaseAgent
from aadap.agents.optimization_agent import OptimizationAgent
from aadap.core.config import get_settings
from aadap.core.logging import get_logger
from aadap.db.models import ApprovalRequest, Artifact, Execution, Task
from aadap.db.session import get_db_session
from aadap.integrations.databricks_client import (
    BaseDatabricksClient,
    DatabricksClient,
    JobStatus,
)
from aadap.integrations.fabric_client import (
    BaseFabricClient,
    FabricClient,
    JobStatus as FabricJobStatus,
)
from aadap.integrations.llm_client import (
    AzureOpenAIClient,
    BaseLLMClient,
)
from aadap.orchestrator.events import EventStore
from aadap.orchestrator.state_machine import TaskState, TaskStateMachine
from aadap.safety.approval_engine import (
    OperationRequest,
    get_approval_engine,
)
from aadap.safety.static_analysis import StaticAnalyzer

logger = get_logger(__name__)


from aadap.orchestrator.routing import CAPABILITY_TASK_TYPES, route_task
from aadap.core.task_types import TaskMode, OperationType, is_direct_execution


_DIRECT_EXECUTION_OPERATIONS = {
    OperationType.LIST_TABLES,
    OperationType.LIST_FILES,
    OperationType.LIST_NOTEBOOKS,
    OperationType.LIST_PIPELINES,
    OperationType.LIST_JOBS,
    OperationType.PREVIEW_TABLE,
    OperationType.GET_SCHEMA,
}


# ── SQL Code Generation Prompt ──────────────────────────────────────────

_SQL_SYSTEM_PROMPT = (
    "You are an expert Databricks SQL developer. Generate production-quality "
    "SQL code for data engineering tasks on Azure Databricks SQL Warehouse.\n\n"
    "RULES:\n"
    "- Output ONLY the SQL code, no markdown fences, no explanation.\n"
    "- The SQL must be valid Databricks SQL / Spark SQL syntax.\n"
    "- Include comments in the SQL for clarity.\n"
    "- If the task is ambiguous, make reasonable assumptions and document them in SQL comments.\n"
)

_PYTHON_SYSTEM_PROMPT = (
    "You are an expert Databricks Python/PySpark developer. Generate production-quality "
    "Python code for data engineering tasks on Azure Databricks.\n\n"
    "RULES:\n"
    "- Output ONLY the Python code, no markdown fences, no explanation.\n"
    "- Use PySpark APIs where applicable.\n"
    "- Include error handling.\n"
    "- If the task is ambiguous, make reasonable assumptions and document them in comments.\n"
)

_FABRIC_PYTHON_SYSTEM_PROMPT = (
    "You are an expert Microsoft Fabric Python/PySpark developer. Generate production-quality "
    "Python code for data engineering tasks on Microsoft Fabric Spark notebooks.\n\n"
    "RULES:\n"
    "- Output ONLY the Python code, no markdown fences, no explanation.\n"
    "- Use PySpark APIs where applicable.\n"
    "- Use Fabric-native APIs: notebookutils, mssparkutils, sempy.\n"
    "- Access Lakehouse tables via spark.read.table() or spark.sql().\n"
    "- Include error handling.\n"
    "- Do NOT use dbutils — use notebookutils or mssparkutils instead.\n"
    "- If the task is ambiguous, make reasonable assumptions and document them in comments.\n"
)

_FABRIC_SCALA_SYSTEM_PROMPT = (
    "You are an expert Microsoft Fabric Scala/Spark developer. Generate production-quality "
    "Scala code for data processing tasks on Microsoft Fabric Spark notebooks.\n\n"
    "RULES:\n"
    "- Output ONLY the Scala code, no markdown fences, no explanation.\n"
    "- Use Spark DataFrame API for data operations.\n"
    "- Access Lakehouse tables via spark.read.table() or spark.sql().\n"
    "- Include proper type annotations and error handling.\n"
    "- Prefer functional style: map, flatMap, filter.\n"
    "- If the task is ambiguous, make reasonable assumptions and document them in comments.\n"
)

_FABRIC_SQL_SYSTEM_PROMPT = (
    "You are an expert Microsoft Fabric SQL developer. Generate production-quality "
    "SQL queries for Fabric Lakehouse SQL endpoint or Warehouse.\n\n"
    "RULES:\n"
    "- Output ONLY the SQL code, no markdown fences, no explanation.\n"
    "- Use T-SQL or Spark SQL syntax as appropriate for Fabric.\n"
    "- Include comments in the SQL for clarity.\n"
    "- Leverage Delta Lake features (MERGE, TIME TRAVEL) where appropriate.\n"
    "- If the task is ambiguous, make reasonable assumptions and document them in comments.\n"
)


def _build_code_gen_prompt(
    title: str,
    description: str | None,
    environment: str,
    language: str,
    platform: str = "databricks",
) -> str:
    """Build a prompt for code generation from task metadata."""
    if platform == "fabric":
        system_prompts = {
            "sql": _FABRIC_SQL_SYSTEM_PROMPT,
            "scala": _FABRIC_SCALA_SYSTEM_PROMPT,
            "python": _FABRIC_PYTHON_SYSTEM_PROMPT,
        }
        system = system_prompts.get(language, _FABRIC_PYTHON_SYSTEM_PROMPT)
    else:
        system = _SQL_SYSTEM_PROMPT if language == "sql" else _PYTHON_SYSTEM_PROMPT
    task_block = f"Task: {title}"
    if description:
        task_block += f"\n\nDetails:\n{description}"
    task_block += f"\n\nTarget environment: {environment}"
    task_block += f"\nPlatform: {platform.title()}"
    return f"{system}\n\n{task_block}\n"


# ── Execution Service ──────────────────────────────────────────────────


class ExecutionService:
    """
    End-to-end task execution service.

    Drives a task through the 25-state machine from SUBMITTED → COMPLETED,
    coordinating LLM code generation, safety analysis, Databricks execution,
    and artifact persistence.
    """

    def __init__(
        self,
        llm_client: BaseLLMClient,
        databricks_client: BaseDatabricksClient,
        fabric_client: BaseFabricClient | None = None,
    ) -> None:
        self._llm = llm_client
        self._dbx = databricks_client
        self._fabric = fabric_client
        self._analyzer = StaticAnalyzer()
        self._event_store = EventStore(get_db_session)
        self._approval_engine = get_approval_engine()

    @classmethod
    def create(cls) -> "ExecutionService":
        """
        Factory: build from application settings.

        Real integrations are mandatory in control-plane execution paths.
        Missing configuration fails closed.
        """
        settings = get_settings()

        missing: list[str] = []
        if not settings.azure_openai_api_key:
            missing.append("AADAP_AZURE_OPENAI_API_KEY")
        if not settings.azure_openai_endpoint:
            missing.append("AADAP_AZURE_OPENAI_ENDPOINT")
        if not settings.azure_openai_deployment_name:
            missing.append("AADAP_AZURE_OPENAI_DEPLOYMENT_NAME")
        if not settings.databricks_host:
            missing.append("AADAP_DATABRICKS_HOST")
        if not settings.fabric_tenant_id:
            missing.append("AADAP_FABRIC_TENANT_ID")
        if not settings.fabric_client_id:
            missing.append("AADAP_FABRIC_CLIENT_ID")
        if not settings.fabric_client_secret:
            missing.append("AADAP_FABRIC_CLIENT_SECRET")
        if not settings.fabric_workspace_id:
            missing.append("AADAP_FABRIC_WORKSPACE_ID")

        if missing:
            raise RuntimeError(
                "ExecutionService requires real integration configuration. "
                f"Missing: {', '.join(missing)}"
            )

        llm: BaseLLMClient = AzureOpenAIClient.from_settings()
        dbx: BaseDatabricksClient = DatabricksClient.from_settings()
        fabric: BaseFabricClient | None = FabricClient.from_settings()

        logger.info("execution_service.llm", client="AzureOpenAI")
        logger.info("execution_service.databricks", client="Real")
        logger.info("execution_service.fabric", client="Real")

        return cls(llm_client=llm, databricks_client=dbx, fabric_client=fabric)

    # ── Public API ──────────────────────────────────────────────────────

    async def execute_task(self, task_id: uuid.UUID) -> dict[str, Any]:
        """
        Drive a task through the full execution pipeline.

        Returns a summary dict with final status, output, artifacts, etc.

        The caller (API route) can stream intermediate status via polling.
        """
        logger.info("execution.start", task_id=str(task_id))

        try:
            # 1. Load task
            task = await self._load_task(task_id)
            current_state = getattr(
                task, "current_state", TaskState.SUBMITTED.value)

            if current_state in {
                TaskState.APPROVAL_PENDING.value,
                TaskState.IN_REVIEW.value,
                TaskState.APPROVED.value,
            }:
                return await self._resume_after_approval(task)

            language = self._detect_language(task)
            platform = self._detect_platform(task)

            # 2. SUBMITTED → PARSING
            await self._transition(task_id, TaskState.SUBMITTED, TaskState.PARSING)

            # 3. PARSING → PARSED  (parse / validate the requirement)
            await self._transition(task_id, TaskState.PARSING, TaskState.PARSED)

            # 4. PARSED → PLANNING
            await self._transition(task_id, TaskState.PARSED, TaskState.PLANNING)

            # 5. PLANNING → PLANNED
            await self._transition(task_id, TaskState.PLANNING, TaskState.PLANNED)

            # 6. PLANNED → AGENT_ASSIGNMENT
            await self._transition(task_id, TaskState.PLANNED, TaskState.AGENT_ASSIGNMENT)

            # 7. AGENT_ASSIGNMENT → AGENT_ASSIGNED
            await self._transition(task_id, TaskState.AGENT_ASSIGNMENT, TaskState.AGENT_ASSIGNED)

            # 8. AGENT_ASSIGNED → IN_DEVELOPMENT
            await self._transition(task_id, TaskState.AGENT_ASSIGNED, TaskState.IN_DEVELOPMENT)

            task_mode = self._detect_task_mode(task)
            operation_type = self._detect_operation_type(task)

            if is_direct_execution(task_mode, operation_type):
                return await self._execute_direct_operation(
                    task=task,
                    task_mode=task_mode,
                    operation_type=operation_type,
                )

            # 9. Route to capability agent (if applicable) and generate code
            task_type = self._classify_task_type(task)
            capability_artifacts: list[dict[str, Any]] = []
            if task_type in CAPABILITY_TASK_TYPES:
                code, capability_artifacts = await self._execute_capability_agent(
                    task=task,
                    task_type=task_type,
                    platform=platform,
                    language=language,
                )
            else:
                code = await self._generate_code(task, language, platform)

            # 10. Store generated code as artifact
            code_artifact_id = await self._store_artifact(
                task_id=task_id,
                artifact_type="generated_code",
                name=f"generated_code.{'sql' if language == 'sql' else 'py'}",
                content=code,
                metadata={
                    "language": language,
                    "task_type": task_type,
                    "platform": platform,
                },
            )

            # Persist additional capability artifacts (pipeline_definition,
            # job_config, ingestion_config, etc.)
            if capability_artifacts:
                await self._persist_capability_artifacts(
                    task_id=task_id,
                    artifacts=capability_artifacts,
                )

            # 11. IN_DEVELOPMENT → CODE_GENERATED
            await self._transition(task_id, TaskState.IN_DEVELOPMENT, TaskState.CODE_GENERATED)

            # 12. CODE_GENERATED → IN_VALIDATION  (safety analysis)
            await self._transition(task_id, TaskState.CODE_GENERATED, TaskState.IN_VALIDATION)

            # 13. Run safety analysis (Gates 1-3)
            risk_result = self._analyzer.evaluate(code, language=language)

            # Store validation report artifact
            await self._store_artifact(
                task_id=task_id,
                artifact_type="validation_report",
                name="safety_analysis_report.json",
                content=json.dumps({
                    "passed": risk_result.passed,
                    "risk_level": risk_result.risk_level.value,
                    "findings": [
                        {
                            "line": f.line,
                            "pattern": f.pattern,
                            "description": f.description,
                            "severity": f.severity.value,
                        }
                        for f in risk_result.findings
                    ],
                }, indent=2),
                metadata={"gate": "static_analysis"},
            )

            # 14. IN_VALIDATION → VALIDATION_PASSED (or VALIDATION_FAILED)
            if not risk_result.passed:
                await self._transition(task_id, TaskState.IN_VALIDATION, TaskState.VALIDATION_FAILED)
                return {
                    "task_id": str(task_id),
                    "status": "VALIDATION_FAILED",
                    "risk_level": risk_result.risk_level.value,
                    "findings": len(risk_result.findings),
                    "message": "Code failed safety analysis. Review findings and resubmit.",
                }

            await self._transition(task_id, TaskState.IN_VALIDATION, TaskState.VALIDATION_PASSED)

            # 15. Optimization phase (Phase 8)
            await self._transition(
                task_id,
                TaskState.VALIDATION_PASSED,
                TaskState.OPTIMIZATION_PENDING,
            )
            await self._transition(
                task_id,
                TaskState.OPTIMIZATION_PENDING,
                TaskState.IN_OPTIMIZATION,
            )

            optimized_code, optimization_summary = await self._run_optimization_phase(
                task=task,
                code=code,
                language=language,
                platform=platform,
            )

            await self._store_artifact(
                task_id=task_id,
                artifact_type="optimized_code",
                name=f"optimized_code.{'sql' if language == 'sql' else 'py'}",
                content=optimized_code,
                metadata={
                    "language": language,
                    "platform": platform,
                    **optimization_summary,
                },
            )

            await self._store_artifact(
                task_id=task_id,
                artifact_type="optimization_report",
                name="optimization_report.json",
                content=json.dumps(optimization_summary, indent=2),
                metadata={"task_type": task_type},
            )

            await self._transition(
                task_id,
                TaskState.IN_OPTIMIZATION,
                TaskState.OPTIMIZED,
            )

            # 16. OPTIMIZED → approval gate (INV-01)
            task = await self._load_task(task_id)  # Reload for latest state

            approval_record = await self._approval_engine.request_approval_async(
                OperationRequest(
                    task_id=task_id,
                    operation_type=self._classify_operation_type(
                        code=optimized_code,
                        environment=task.environment,
                        task_type=task_type,
                    ),
                    environment=task.environment,
                    code=optimized_code,
                    requested_by="execution_service",
                    metadata={
                        "platform": platform,
                        "language": language,
                        "task_type": task_type,
                    },
                ),
            )

            decision_explanation_artifact_id = await self._store_artifact(
                task_id=task_id,
                artifact_type="decision_explanation",
                name="decision_explanation.json",
                content=json.dumps(
                    {
                        "task_id": str(task_id),
                        "task_type": task_type,
                        "environment": task.environment,
                        "platform": platform,
                        "language": language,
                        "operation_type": approval_record.operation_type,
                        "approval_required": approval_record.status.value == "PENDING",
                        "decision_reason": (
                            approval_record.decision_reason
                            or "Awaiting explicit human decision"
                        ),
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    },
                    indent=2,
                ),
                metadata={
                    "source": "execution_service",
                    "invariant": "INV-09",
                    "approval_id": str(approval_record.id),
                },
            )

            await self._set_task_metadata(
                task_id,
                {
                    "approval_id": str(approval_record.id),
                    "decision_explanation_artifact_id": str(decision_explanation_artifact_id),
                    "platform": platform,
                    "language": language,
                },
            )

            await self._update_approval_explanation(
                approval_id=approval_record.id,
                explanation_artifact_id=decision_explanation_artifact_id,
            )

            await self._transition(task_id, TaskState.OPTIMIZED, TaskState.APPROVAL_PENDING)

            if approval_record.status.value == "PENDING":
                return {
                    "task_id": str(task_id),
                    "status": "APPROVAL_PENDING",
                    "message": "Production task requires human approval before execution.",
                    "code": optimized_code,
                    "language": language,
                }

            # Sandbox/policy auto-approval is explicit and traceable.
            await self._transition(task_id, TaskState.APPROVAL_PENDING, TaskState.IN_REVIEW)
            await self._transition(task_id, TaskState.IN_REVIEW, TaskState.APPROVED)
            execution_result = await self._deploy_approved_code(
                task=task,
                code=optimized_code,
                language=language,
                platform=platform,
                code_artifact_id=code_artifact_id,
                decision_explanation_artifact_id=decision_explanation_artifact_id,
            )

            if execution_result["status"] == "FAILED":
                platform_name = "Fabric" if platform == "fabric" else "Databricks"
                return {
                    "task_id": str(task_id),
                    "status": "DEV_FAILED",
                    "error": execution_result.get("error"),
                    "message": f"{platform_name} execution failed.",
                }

            logger.info("execution.completed", task_id=str(task_id))

            return {
                "task_id": str(task_id),
                "status": "COMPLETED",
                "output": execution_result.get("output"),
                "job_id": execution_result.get("job_id"),
                "duration_ms": execution_result.get("duration_ms"),
                "language": language,
                "code": optimized_code,
                "task_type": task_type,
            }

        except Exception as exc:
            logger.error(
                "execution.error",
                task_id=str(task_id),
                error=str(exc),
            )
            # Try to transition to CANCELLED if possible
            try:
                current = await self._event_store.replay(task_id)
                allowed = TaskStateMachine.get_allowed_transitions(current)
                if TaskState.CANCELLED in allowed:
                    await self._transition(task_id, current, TaskState.CANCELLED)
                elif TaskState.DEV_FAILED in allowed:
                    await self._transition(task_id, current, TaskState.DEV_FAILED)
            except Exception:
                pass  # Best effort
            return {
                "task_id": str(task_id),
                "status": "FAILED",
                "error": str(exc),
            }

    async def _resume_after_approval(self, task: Task) -> dict[str, Any]:
        """Resume execution once an existing approval has been decided."""
        metadata = task.metadata_ or {}
        approval_id_raw = metadata.get("approval_id")
        explanation_id_raw = metadata.get("decision_explanation_artifact_id")
        if not isinstance(approval_id_raw, str) or not approval_id_raw.strip():
            raise RuntimeError(
                "Approval metadata missing: approval_id is required before deployment."
            )
        if not isinstance(explanation_id_raw, str) or not explanation_id_raw.strip():
            raise RuntimeError(
                "INV-09 violation: decision_explanation_artifact_id is required before deployment."
            )

        try:
            approval_id = uuid.UUID(approval_id_raw)
        except ValueError as exc:
            raise RuntimeError(
                "Approval metadata invalid: approval_id must be a UUID."
            ) from exc
        try:
            explanation_artifact_id = uuid.UUID(explanation_id_raw)
        except ValueError as exc:
            raise RuntimeError(
                "INV-09 violation: decision_explanation_artifact_id must be a UUID."
            ) from exc

        await self._load_artifact_by_id(explanation_artifact_id)

        try:
            approval_request = await self._load_approval_request(approval_id)
        except RuntimeError:
            return {
                "task_id": str(task.id),
                "status": "APPROVAL_PENDING",
                "message": "Approval record not persisted yet. Execution remains blocked.",
            }

        if approval_request.status == "PENDING":
            return {
                "task_id": str(task.id),
                "status": "APPROVAL_PENDING",
                "message": "Approval is still pending. Execution remains blocked.",
            }
        if approval_request.status == "REJECTED":
            current_state = getattr(
                task, "current_state", TaskState.APPROVAL_PENDING.value)
            if current_state != TaskState.REJECTED.value:
                await self._transition(task.id, current_state, TaskState.REJECTED)
            return {
                "task_id": str(task.id),
                "status": "REJECTED",
                "error": approval_request.decision_reason or "Approval was rejected.",
            }
        if approval_request.status != "APPROVED":
            raise RuntimeError(
                f"Unsupported approval status '{approval_request.status}' for deployment."
            )

        current_state = getattr(task, "current_state",
                                TaskState.APPROVAL_PENDING.value)
        if current_state == TaskState.APPROVAL_PENDING.value:
            await self._transition(task.id, TaskState.APPROVAL_PENDING, TaskState.IN_REVIEW)
            await self._transition(task.id, TaskState.IN_REVIEW, TaskState.APPROVED)
            task = await self._load_task(task.id)
        elif current_state == TaskState.IN_REVIEW.value:
            await self._transition(task.id, TaskState.IN_REVIEW, TaskState.APPROVED)
            task = await self._load_task(task.id)

        code_artifact = await self._load_latest_code_artifact(task.id)
        execution_result = await self._deploy_approved_code(
            task=task,
            code=code_artifact.content or "",
            language=str((code_artifact.metadata_ or {}).get(
                "language") or self._detect_language(task)),
            platform=str((code_artifact.metadata_ or {}).get(
                "platform") or self._detect_platform(task)),
            code_artifact_id=code_artifact.id,
            decision_explanation_artifact_id=explanation_artifact_id,
        )

        if execution_result["status"] == "FAILED":
            return {
                "task_id": str(task.id),
                "status": "DEV_FAILED",
                "error": execution_result.get("error"),
            }

        return {
            "task_id": str(task.id),
            "status": "COMPLETED",
            "output": execution_result.get("output"),
            "job_id": execution_result.get("job_id"),
            "duration_ms": execution_result.get("duration_ms"),
            "language": (code_artifact.metadata_ or {}).get("language"),
            "code": code_artifact.content,
        }

    async def _deploy_approved_code(
        self,
        task: Task,
        code: str,
        language: str,
        platform: str,
        code_artifact_id: uuid.UUID | None,
        decision_explanation_artifact_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Deploy code after approval has been explicitly granted."""
        await self._transition(task.id, TaskState.APPROVED, TaskState.DEPLOYING)

        if platform == "fabric":
            execution_result = await self._execute_on_fabric(
                task_id=task.id,
                code=code,
                environment=task.environment,
                language=language,
                code_artifact_id=code_artifact_id,
            )
        else:
            execution_result = await self._execute_on_databricks(
                task_id=task.id,
                code=code,
                environment=task.environment,
                language=language,
                code_artifact_id=code_artifact_id,
            )

        if execution_result["status"] == "FAILED":
            await self._transition(task.id, TaskState.DEPLOYING, TaskState.DEV_FAILED)
            return execution_result

        await self._transition(task.id, TaskState.DEPLOYING, TaskState.DEPLOYED)
        await self._store_artifact(
            task_id=task.id,
            artifact_type="execution_result",
            name="execution_output.txt",
            content=execution_result.get("output", ""),
            metadata={
                "job_id": execution_result.get("job_id"),
                "duration_ms": execution_result.get("duration_ms"),
                "language": language,
                "decision_explanation_artifact_id": (
                    str(decision_explanation_artifact_id)
                    if decision_explanation_artifact_id is not None
                    else None
                ),
            },
        )
        await self._transition(task.id, TaskState.DEPLOYED, TaskState.COMPLETED)
        return execution_result

    async def _set_task_metadata(
        self,
        task_id: uuid.UUID,
        updates: dict[str, Any],
    ) -> None:
        """Merge and persist task metadata fields."""
        from sqlalchemy import select, update

        async with get_db_session() as session:
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            if task is None:
                raise ValueError(f"Task {task_id} not found")
            merged = dict(task.metadata_ or {})
            merged.update(updates)
            await session.execute(
                update(Task)
                .where(Task.id == task_id)
                .values(metadata_=merged)
            )

    async def _load_latest_code_artifact(self, task_id: uuid.UUID) -> Artifact:
        """Load latest optimized_code or generated_code artifact for a task."""
        from sqlalchemy import desc, select

        async with get_db_session() as session:
            result = await session.execute(
                select(Artifact)
                .where(
                    Artifact.task_id == task_id,
                    Artifact.artifact_type.in_(
                        ["optimized_code", "generated_code"]),
                )
                .order_by(desc(Artifact.created_at))
                .limit(1)
            )
            artifact = result.scalar_one_or_none()
            if artifact is None:
                raise RuntimeError(
                    "Missing deployable code artifact for approved task.")
            return artifact

    async def _load_artifact_by_id(self, artifact_id: uuid.UUID) -> Artifact:
        """Load artifact by ID or fail closed."""
        from sqlalchemy import select

        async with get_db_session() as session:
            result = await session.execute(
                select(Artifact).where(Artifact.id == artifact_id)
            )
            artifact = result.scalar_one_or_none()
            if artifact is None:
                raise RuntimeError(
                    f"INV-09 violation: artifact {artifact_id} not found."
                )
            return artifact

    async def _update_approval_explanation(
        self,
        approval_id: uuid.UUID,
        explanation_artifact_id: uuid.UUID,
    ) -> None:
        """Update approval request with explanation artifact ID (INV-09)."""
        from sqlalchemy import update

        async with get_db_session() as session:
            await session.execute(
                update(ApprovalRequest)
                .where(ApprovalRequest.id == approval_id)
                .values(explanation_artifact_id=explanation_artifact_id)
            )

    async def _load_approval_request(self, approval_id: uuid.UUID) -> ApprovalRequest:
        """Load persisted approval request or fail closed."""
        from sqlalchemy import select

        async with get_db_session() as session:
            result = await session.execute(
                select(ApprovalRequest).where(
                    ApprovalRequest.id == approval_id)
            )
            approval = result.scalar_one_or_none()
            if approval is None:
                raise RuntimeError(
                    f"Approval request {approval_id} not found in persistence store."
                )
            return approval

    @staticmethod
    def _classify_operation_type(
        code: str,
        environment: str,
        task_type: str,
    ) -> str:
        """Classify operation type for approval policy enforcement."""
        lowered = code.lower()
        destructive_tokens = ["drop ", "truncate ", "delete ", "revoke "]
        if any(token in lowered for token in destructive_tokens):
            return "destructive"
        if task_type == "catalog" and any(tok in lowered for tok in ["grant ", "revoke "]):
            return "permission_change"
        if task_type == "catalog" and any(tok in lowered for tok in ["create schema", "alter table", "create table"]):
            return "schema_change"
        if environment.upper() == "PRODUCTION":
            return "write"
        return "read_only"

    @staticmethod
    def _is_generate_only(task: Task) -> bool:
        """Return True only when generate_only is explicitly enabled."""
        raw = (task.metadata_ or {}).get("generate_only", False)
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return False

    # ── Internal Helpers ────────────────────────────────────────────────

    async def _load_task(self, task_id: uuid.UUID) -> Task:
        """Load a Task from the database."""
        from sqlalchemy import select
        async with get_db_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            task = result.scalar_one_or_none()
            if task is None:
                raise ValueError(f"Task {task_id} not found")
            return task

    def _detect_language(self, task: Task) -> str:
        """Detect the target language from task metadata or agent_type."""
        meta = task.metadata_ or {}
        agent_type = meta.get("agent_type", "")

        # Explicit language in metadata
        if "language" in meta:
            return meta["language"]

        # Infer from agent_type
        if "python" in agent_type.lower() or "pyspark" in agent_type.lower():
            return "python"
        if "scala" in agent_type.lower():
            return "scala"

        # Default to SQL
        return "sql"

    def _detect_platform(self, task: Task) -> str:
        """Detect the target platform from task metadata or agent_type."""
        meta = task.metadata_ or {}
        agent_type = meta.get("agent_type", "")

        # Explicit platform in metadata
        if "platform" in meta:
            return meta["platform"].lower()

        # Infer from agent_type
        if "fabric" in agent_type.lower():
            return "fabric"

        # Default to Databricks
        return "databricks"

    def _detect_task_mode(self, task: Task) -> TaskMode | None:
        """Detect the task mode from task metadata."""
        meta = task.metadata_ or {}
        task_mode = meta.get("task_mode")
        if task_mode:
            try:
                return TaskMode(task_mode)
            except ValueError:
                pass
        return None

    def _detect_operation_type(self, task: Task) -> OperationType | None:
        """Detect the operation type from task metadata."""
        meta = task.metadata_ or {}
        operation_type = meta.get("operation_type")
        if operation_type:
            try:
                return OperationType(operation_type)
            except ValueError:
                pass
        return None

    async def _execute_direct_operation(
        self,
        task: Task,
        task_mode: TaskMode | None,
        operation_type: OperationType | None,
    ) -> dict[str, Any]:
        """Execute read/list operations directly without code generation."""
        from aadap.services.databricks_explorer import DatabricksExplorerService
        from aadap.services.fabric_explorer import FabricExplorerService
        
        platform = self._detect_platform(task)
        meta = task.metadata_ or {}
        catalog = meta.get("catalog")
        schema_name = meta.get("schema_name")
        table = meta.get("table")
        
        result_data: dict[str, Any] = {}
        
        try:
            if platform == "fabric":
                if self._fabric is None:
                    raise RuntimeError("Fabric client not configured")
                explorer = FabricExplorerService(self._fabric)
            else:
                explorer = DatabricksExplorerService(self._dbx)
            
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
            elif operation_type == OperationType.LIST_SCHEMAS and catalog:
                schemas = await explorer.list_schemas(catalog)
                result_data = {
                    "schemas": [
                        {
                            "id": s.id,
                            "name": s.name,
                            "catalog_id": s.catalog_id,
                        }
                        for s in schemas
                    ]
                }
            elif operation_type == OperationType.LIST_CATALOGS:
                if platform == "fabric":
                    catalogs = await explorer.list_workspaces()
                else:
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
                    "message": f"Direct execution for {operation_type} not yet implemented",
                    "catalog": catalog,
                    "schema": schema_name,
                    "table": table,
                }
            
            await self._transition(task.id, TaskState.IN_DEVELOPMENT, TaskState.CODE_GENERATED)
            await self._transition(task.id, TaskState.CODE_GENERATED, TaskState.IN_VALIDATION)
            await self._transition(task.id, TaskState.IN_VALIDATION, TaskState.VALIDATION_PASSED)
            await self._transition(task.id, TaskState.VALIDATION_PASSED, TaskState.OPTIMIZATION_PENDING)
            await self._transition(task.id, TaskState.OPTIMIZATION_PENDING, TaskState.IN_OPTIMIZATION)
            await self._transition(task.id, TaskState.IN_OPTIMIZATION, TaskState.OPTIMIZED)
            await self._transition(task.id, TaskState.OPTIMIZED, TaskState.APPROVAL_PENDING)
            await self._transition(task.id, TaskState.APPROVAL_PENDING, TaskState.IN_REVIEW)
            await self._transition(task.id, TaskState.IN_REVIEW, TaskState.APPROVED)
            await self._transition(task.id, TaskState.APPROVED, TaskState.DEPLOYING)
            
            await self._store_artifact(
                task_id=task.id,
                artifact_type="execution_result",
                name=f"{operation_type or 'direct'}_result.json",
                content=json.dumps(result_data, indent=2),
                metadata={
                    "task_mode": task_mode.value if task_mode else None,
                    "operation_type": operation_type.value if operation_type else None,
                    "platform": platform,
                },
            )
            
            await self._transition(task.id, TaskState.DEPLOYING, TaskState.DEPLOYED)
            await self._transition(task.id, TaskState.DEPLOYED, TaskState.COMPLETED)
            
            logger.info(
                "execution.direct_completed",
                task_id=str(task.id),
                operation_type=operation_type.value if operation_type else None,
                platform=platform,
            )
            
            return {
                "task_id": str(task.id),
                "status": "COMPLETED",
                "output": json.dumps(result_data, indent=2),
                "task_mode": task_mode.value if task_mode else None,
                "operation_type": operation_type.value if operation_type else None,
            }
            
        except Exception as exc:
            logger.error(
                "execution.direct_error",
                task_id=str(task.id),
                error=str(exc),
            )
            current = await self._event_store.replay(task.id)
            if TaskState.DEV_FAILED in TaskStateMachine.get_allowed_transitions(current):
                await self._transition(task.id, current, TaskState.DEV_FAILED)
            return {
                "task_id": str(task.id),
                "status": "FAILED",
                "error": str(exc),
            }

    def _classify_task_type(self, task: Task) -> str:
        """Classify the task for capability routing.

        Uses the TaskRouter which integrates deterministic keyword matching
        with LLM-based orchestration for ambiguous cases.

        Returns one of:
        - ingestion, etl_pipeline, job_scheduler, catalog
        - developer (fallback for generic codegen)
        """
        decision = route_task(
            task_id=task.id,
            title=task.title or "",
            description=task.description or "",
            metadata=task.metadata_,
            environment=task.environment,
        )
        logger.info(
            "execution.routing_decision",
            task_id=str(task.id),
            agent_type=decision.agent_type,
            confidence=decision.confidence,
            method=decision.routing_method,
        )
        return decision.agent_type

    def _get_capability_agent(
        self,
        task_type: str,
        platform: str,
        environment: str,
        generate_only: bool = False,
    ) -> BaseAgent | None:
        """Return the capability agent instance for the given task type."""
        if task_type not in CAPABILITY_TASK_TYPES:
            return None

        adapter: PlatformAdapter | None = None
        if not generate_only:
            adapter = self._build_platform_adapter(platform)

        if task_type == "ingestion":
            return IngestionAgent(
                agent_id=f"exec-ingestion-{uuid.uuid4().hex[:8]}",
                llm_client=self._llm,
                platform_adapter=adapter,
            )
        if task_type == "etl_pipeline":
            return ETLPipelineAgent(
                agent_id=f"exec-etl-{uuid.uuid4().hex[:8]}",
                llm_client=self._llm,
                platform_adapter=adapter,
            )
        if task_type == "job_scheduler":
            return JobSchedulerAgent(
                agent_id=f"exec-scheduler-{uuid.uuid4().hex[:8]}",
                llm_client=self._llm,
                platform_adapter=adapter,
            )
        if task_type == "catalog":
            return CatalogAgent(
                agent_id=f"exec-catalog-{uuid.uuid4().hex[:8]}",
                llm_client=self._llm,
                platform_adapter=adapter,
            )
        return None

    def _build_platform_adapter(self, platform: str) -> PlatformAdapter:
        """Build a concrete platform adapter for capability execution mode."""
        platform_normalized = platform.lower()
        if platform_normalized == "fabric":
            if self._fabric is None:
                raise RuntimeError(
                    "Capability execution requires Fabric client configuration."
                )
            return FabricAdapter(client=self._fabric)
        return DatabricksAdapter(client=self._dbx)

    async def _execute_capability_agent(
        self,
        task: Task,
        task_type: str,
        platform: str,
        language: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Execute a capability agent and return generated code + artifacts."""
        agent = self._get_capability_agent(
            task_type=task_type,
            platform=platform,
            environment=task.environment,
            generate_only=self._is_generate_only(task),
        )
        if agent is None:
            return await self._generate_code(task, language, platform), []

        task_data = {
            "title": task.title,
            "description": task.description or "",
            "platform": platform,
            "environment": task.environment,
            **(task.metadata_ or {}),
        }
        capability_config = task_data.get("capability_config")
        if isinstance(capability_config, dict):
            task_data.update(capability_config)

        context = AgentContext(
            task_id=task.id,
            task_data=task_data,
            token_budget=task.token_budget,
            allowed_tools=set(),
            metadata={"source": "execution_service", "task_type": task_type},
        )

        await agent.accept_task(context)
        result = await agent.execute(context)

        if not result.success:
            raise RuntimeError(
                result.error or "Capability agent execution failed")

        output = result.output if isinstance(result.output, dict) else {}
        code = output.get("code")
        if not isinstance(code, str) or not code.strip():
            code = json.dumps(output, indent=2)

        return code, result.artifacts

    async def _persist_capability_artifacts(
        self,
        task_id: uuid.UUID,
        artifacts: list[dict[str, Any]],
    ) -> None:
        """Persist capability-agent artifacts, including new artifact types."""
        for index, artifact in enumerate(artifacts, start=1):
            artifact_type = str(artifact.get("type", "agent_artifact"))
            content_obj = artifact.get("content", artifact)
            content = (
                content_obj
                if isinstance(content_obj, str)
                else json.dumps(content_obj, indent=2)
            )
            await self._store_artifact(
                task_id=task_id,
                artifact_type=artifact_type,
                name=f"{artifact_type}_{index}.json",
                content=content,
                metadata={
                    "source": "capability_agent",
                    "artifact_type": artifact_type,
                },
            )

    async def _run_optimization_phase(
        self,
        task: Task,
        code: str,
        language: str,
        platform: str,
    ) -> tuple[str, dict[str, Any]]:
        """Run optimization phase after validation.

        Returns ``(optimized_code, optimization_summary)``.
        Falls back to the original code if optimization cannot be produced.
        """
        if language not in {"python", "scala"}:
            return code, {
                "applied": False,
                "reason": "Language not supported for optimization",
                "platform": platform,
            }

        optimization_agent = OptimizationAgent(
            agent_id=f"exec-opt-{uuid.uuid4().hex[:8]}",
            llm_client=self._llm,
        )
        context = AgentContext(
            task_id=task.id,
            task_data={
                "code": code,
                "platform": platform,
                "context": task.description or "",
                "environment": task.environment,
            },
            token_budget=task.token_budget,
            allowed_tools=set(),
            metadata={"source": "execution_service"},
        )

        try:
            await optimization_agent.accept_task(context)
            result = await optimization_agent.execute(context)
        except Exception as exc:  # pragma: no cover
            return code, {
                "applied": False,
                "reason": f"Optimization failed: {exc}",
                "platform": platform,
            }

        if not result.success:
            return code, {
                "applied": False,
                "reason": result.error or "Optimization failed",
                "platform": platform,
            }

        output = result.output if isinstance(result.output, dict) else {}
        optimized_code = output.get("optimized_code")
        if not isinstance(optimized_code, str) or not optimized_code.strip():
            return code, {
                "applied": False,
                "reason": "Missing optimized_code in optimization output",
                "platform": platform,
            }

        return optimized_code, {
            "applied": True,
            "platform": platform,
            "changes": output.get("changes", []),
            "expected_improvement": output.get("expected_improvement"),
        }

    async def _transition(
        self,
        task_id: uuid.UUID,
        from_state: TaskState | str,
        to_state: TaskState | str,
    ) -> None:
        """Record a state transition with full audit trail."""
        from_state_enum = (
            from_state
            if isinstance(from_state, TaskState)
            else TaskStateMachine.parse_state(from_state)
        )
        to_state_enum = (
            to_state
            if isinstance(to_state, TaskState)
            else TaskStateMachine.parse_state(to_state)
        )

        await self._event_store.record_transition(
            task_id=task_id,
            from_state=from_state_enum,
            to_state=to_state_enum,
            triggered_by="execution_service",
            reason=f"Automated transition: {from_state_enum.value} → {to_state_enum.value}",
        )
        logger.info(
            "execution.transition",
            task_id=str(task_id),
            from_state=from_state_enum.value,
            to_state=to_state_enum.value,
        )

    async def _generate_code(self, task: Task, language: str, platform: str = "databricks") -> str:
        """Generate code using the LLM for the given task."""
        prompt = _build_code_gen_prompt(
            title=task.title,
            description=task.description,
            environment=task.environment,
            language=language,
            platform=platform,
        )

        response = await self._llm.complete(prompt=prompt, max_tokens=4096)

        code = response.content.strip()

        # Strip markdown code fences if present
        if code.startswith("```"):
            lines = code.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            code = "\n".join(lines)

        # Update token usage on the task
        async with get_db_session() as session:
            from sqlalchemy import update
            await session.execute(
                update(Task)
                .where(Task.id == task.id)
                .values(tokens_used=Task.tokens_used + response.tokens_used)
            )

        logger.info(
            "execution.code_generated",
            task_id=str(task.id),
            language=language,
            tokens_used=response.tokens_used,
            code_length=len(code),
        )

        return code

    async def _store_artifact(
        self,
        task_id: uuid.UUID,
        artifact_type: str,
        name: str,
        content: str,
        metadata: dict | None = None,
    ) -> uuid.UUID:
        """Persist an artifact in the database."""
        artifact_id = uuid.uuid4()
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        async with get_db_session() as session:
            artifact = Artifact(
                id=artifact_id,
                task_id=task_id,
                artifact_type=artifact_type,
                name=name,
                content=content,
                content_hash=content_hash,
                metadata_=metadata or {},
            )
            session.add(artifact)

        logger.info(
            "execution.artifact_stored",
            task_id=str(task_id),
            artifact_id=str(artifact_id),
            artifact_type=artifact_type,
        )
        return artifact_id

    async def _execute_on_databricks(
        self,
        task_id: uuid.UUID,
        code: str,
        environment: str,
        language: str,
        code_artifact_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Submit code to Databricks and wait for result.

        Records an Execution row in the database for audit.
        """
        # Create execution record
        execution_id = uuid.uuid4()
        async with get_db_session() as session:
            execution = Execution(
                id=execution_id,
                task_id=task_id,
                environment=environment,
                status="PENDING",
                code_artifact_id=code_artifact_id,
                started_at=datetime.now(timezone.utc),
            )
            session.add(execution)

        logger.info(
            "execution.databricks_submit",
            task_id=str(task_id),
            execution_id=str(execution_id),
            language=language,
            environment=environment,
        )

        try:
            # Submit to Databricks
            submission = await self._dbx.submit_job(
                task_id=task_id,
                code=code,
                environment=environment,
                language=language,
            )

            # Poll for completion (Databricks mock auto-completes)
            status = await self._dbx.get_job_status(submission.job_id)

            # Get output
            job_result = await self._dbx.get_job_output(submission.job_id)

            # Update execution record
            final_status = "SUCCESS" if job_result.status == JobStatus.SUCCESS else "FAILED"
            async with get_db_session() as session:
                from sqlalchemy import update
                await session.execute(
                    update(Execution)
                    .where(Execution.id == execution_id)
                    .values(
                        status=final_status,
                        output=job_result.output,
                        error=job_result.error,
                        duration_ms=job_result.duration_ms,
                        completed_at=datetime.now(timezone.utc),
                        metadata_={
                            "job_id": submission.job_id,
                            "language": language,
                            **(job_result.metadata or {}),
                        },
                    )
                )

            return {
                "status": final_status,
                "output": job_result.output,
                "error": job_result.error,
                "job_id": submission.job_id,
                "duration_ms": job_result.duration_ms,
            }

        except Exception as exc:
            # Update execution as FAILED
            async with get_db_session() as session:
                from sqlalchemy import update
                await session.execute(
                    update(Execution)
                    .where(Execution.id == execution_id)
                    .values(
                        status="FAILED",
                        error=str(exc),
                        completed_at=datetime.now(timezone.utc),
                    )
                )
            logger.error(
                "execution.databricks_error",
                task_id=str(task_id),
                error=str(exc),
            )
            return {
                "status": "FAILED",
                "error": str(exc),
                "output": None,
                "job_id": None,
                "duration_ms": None,
            }

    async def _execute_on_fabric(
        self,
        task_id: uuid.UUID,
        code: str,
        environment: str,
        language: str,
        code_artifact_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """
        Submit code to Microsoft Fabric and wait for result.

        Records an Execution row in the database for audit.
        """
        if self._fabric is None:
            return {
                "status": "FAILED",
                "error": "Fabric client is not configured",
                "output": None,
                "job_id": None,
                "duration_ms": None,
            }

        # Create execution record
        execution_id = uuid.uuid4()
        async with get_db_session() as session:
            execution = Execution(
                id=execution_id,
                task_id=task_id,
                environment=environment,
                status="PENDING",
                code_artifact_id=code_artifact_id,
                started_at=datetime.now(timezone.utc),
            )
            session.add(execution)

        logger.info(
            "execution.fabric_submit",
            task_id=str(task_id),
            execution_id=str(execution_id),
            language=language,
            environment=environment,
        )

        try:
            # Submit to Fabric
            submission = await self._fabric.submit_job(
                task_id=task_id,
                code=code,
                environment=environment,
                language=language,
            )

            # Poll for completion
            status = await self._fabric.get_job_status(submission.job_id)

            # Get output
            job_result = await self._fabric.get_job_output(submission.job_id)

            # Map to canonical status
            final_status = "SUCCESS" if job_result.status == FabricJobStatus.SUCCESS else "FAILED"
            async with get_db_session() as session:
                from sqlalchemy import update
                await session.execute(
                    update(Execution)
                    .where(Execution.id == execution_id)
                    .values(
                        status=final_status,
                        output=job_result.output,
                        error=job_result.error,
                        duration_ms=job_result.duration_ms,
                        completed_at=datetime.now(timezone.utc),
                        metadata_={
                            "job_id": submission.job_id,
                            "language": language,
                            "platform": "Microsoft Fabric",
                            **(job_result.metadata or {}),
                        },
                    )
                )

            return {
                "status": final_status,
                "output": job_result.output,
                "error": job_result.error,
                "job_id": submission.job_id,
                "duration_ms": job_result.duration_ms,
            }

        except Exception as exc:
            # Update execution as FAILED
            async with get_db_session() as session:
                from sqlalchemy import update
                await session.execute(
                    update(Execution)
                    .where(Execution.id == execution_id)
                    .values(
                        status="FAILED",
                        error=str(exc),
                        completed_at=datetime.now(timezone.utc),
                    )
                )
            logger.error(
                "execution.fabric_error",
                task_id=str(task_id),
                error=str(exc),
            )
            return {
                "status": "FAILED",
                "error": str(exc),
                "output": None,
                "job_id": None,
                "duration_ms": None,
            }
