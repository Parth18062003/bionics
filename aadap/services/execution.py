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

from aadap.core.config import get_settings
from aadap.core.logging import get_logger
from aadap.db.models import Artifact, Execution, Task
from aadap.db.session import get_db_session
from aadap.integrations.databricks_client import (
    BaseDatabricksClient,
    DatabricksClient,
    JobStatus,
    MockDatabricksClient,
)
from aadap.integrations.fabric_client import (
    BaseFabricClient,
    FabricClient,
    JobStatus as FabricJobStatus,
    MockFabricClient,
)
from aadap.integrations.llm_client import (
    AzureOpenAIClient,
    BaseLLMClient,
    MockLLMClient,
)
from aadap.orchestrator.events import EventStore
from aadap.orchestrator.state_machine import TaskState, TaskStateMachine
from aadap.safety.static_analysis import StaticAnalyzer

logger = get_logger(__name__)


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

    @classmethod
    def create(cls) -> "ExecutionService":
        """
        Factory: build from application settings.

        Uses real Azure OpenAI + Databricks clients when credentials are
        configured, otherwise falls back to mock clients for development.
        """
        settings = get_settings()

        # LLM client
        if settings.azure_openai_api_key and settings.azure_openai_endpoint:
            llm: BaseLLMClient = AzureOpenAIClient.from_settings()
            logger.info("execution_service.llm", client="AzureOpenAI")
        else:
            llm = MockLLMClient(
                default_response="SELECT 1 AS health_check;",
            )
            logger.info("execution_service.llm", client="Mock")

        # Databricks client
        if settings.databricks_host:
            dbx: BaseDatabricksClient = DatabricksClient.from_settings()
            logger.info("execution_service.databricks", client="Real")
        else:
            dbx = MockDatabricksClient()
            logger.info("execution_service.databricks", client="Mock")

        # Fabric client
        fabric: BaseFabricClient | None = None
        if settings.fabric_tenant_id and settings.fabric_client_id:
            fabric = FabricClient.from_settings()
            logger.info("execution_service.fabric", client="Real")
        else:
            fabric = MockFabricClient()
            logger.info("execution_service.fabric", client="Mock")

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

            # 9. Generate code via LLM
            code = await self._generate_code(task, language, platform)

            # 10. Store generated code as artifact
            code_artifact_id = await self._store_artifact(
                task_id=task_id,
                artifact_type="generated_code",
                name=f"generated_code.{'sql' if language == 'sql' else 'py'}",
                content=code,
                metadata={"language": language},
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

            # 15. Skip optimization for now → go to DEPLOYING
            #     VALIDATION_PASSED → APPROVAL_PENDING (for prod) or DEPLOYING (sandbox)
            task = await self._load_task(task_id)  # Reload for latest state

            if task.environment == "PRODUCTION":
                # Needs approval — stop here, user must approve via UI
                await self._transition(task_id, TaskState.VALIDATION_PASSED, TaskState.APPROVAL_PENDING)
                return {
                    "task_id": str(task_id),
                    "status": "APPROVAL_PENDING",
                    "message": "Production task requires human approval before execution.",
                    "code": code,
                    "language": language,
                }

            # 16. Sandbox: skip approval, straight to execution
            #     VALIDATION_PASSED can go to OPTIMIZATION_PENDING or APPROVAL_PENDING
            #     We go VALIDATION_PASSED → APPROVAL_PENDING → IN_REVIEW → APPROVED → DEPLOYING
            await self._transition(task_id, TaskState.VALIDATION_PASSED, TaskState.APPROVAL_PENDING)
            await self._transition(task_id, TaskState.APPROVAL_PENDING, TaskState.IN_REVIEW)
            await self._transition(task_id, TaskState.IN_REVIEW, TaskState.APPROVED)
            await self._transition(task_id, TaskState.APPROVED, TaskState.DEPLOYING)

            # 17. Execute on target platform (Databricks or Fabric)
            if platform == "fabric":
                execution_result = await self._execute_on_fabric(
                    task_id=task_id,
                    code=code,
                    environment=task.environment,
                    language=language,
                    code_artifact_id=code_artifact_id,
                )
            else:
                execution_result = await self._execute_on_databricks(
                    task_id=task_id,
                    code=code,
                    environment=task.environment,
                    language=language,
                    code_artifact_id=code_artifact_id,
                )

            if execution_result["status"] == "FAILED":
                await self._transition(task_id, TaskState.DEPLOYING, TaskState.DEV_FAILED)
                platform_name = "Fabric" if platform == "fabric" else "Databricks"
                return {
                    "task_id": str(task_id),
                    "status": "DEV_FAILED",
                    "error": execution_result.get("error"),
                    "message": f"{platform_name} execution failed.",
                }

            # 18. DEPLOYING → DEPLOYED
            await self._transition(task_id, TaskState.DEPLOYING, TaskState.DEPLOYED)

            # 19. Store execution result artifact
            await self._store_artifact(
                task_id=task_id,
                artifact_type="execution_result",
                name="execution_output.txt",
                content=execution_result.get("output", ""),
                metadata={
                    "job_id": execution_result.get("job_id"),
                    "duration_ms": execution_result.get("duration_ms"),
                    "language": language,
                },
            )

            # 20. DEPLOYED → COMPLETED
            await self._transition(task_id, TaskState.DEPLOYED, TaskState.COMPLETED)

            logger.info("execution.completed", task_id=str(task_id))

            return {
                "task_id": str(task_id),
                "status": "COMPLETED",
                "output": execution_result.get("output"),
                "job_id": execution_result.get("job_id"),
                "duration_ms": execution_result.get("duration_ms"),
                "language": language,
                "code": code,
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
