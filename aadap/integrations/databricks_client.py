"""
AADAP — Databricks Execution Client
=======================================
Abstraction layer for Databricks job submission and monitoring.

Architecture layer: L3 (Integration).
Phase 7 contract: Databricks execution integration.

Enforces:
- INV-05: Sandbox isolated from production data
- Correlation ID forwarded via custom tags

Supports:
- SQL execution via SQL Warehouse (Statement Execution API)
- Python execution via Compute Cluster (Command Execution API)

Usage:
    client = MockDatabricksClient()
    result = await client.submit_job(task_id, code, "SANDBOX")
    status = await client.get_job_status(result.job_id)

    # Real client:
    client = DatabricksClient.from_settings()
    # SQL execution
    result = await client.submit_job(task_id, "SELECT 1", "SANDBOX", language="sql")
    # Python execution
    result = await client.submit_job(task_id, "print('hello')", "SANDBOX", language="python")
"""

from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from aadap.core.config import get_settings
from aadap.core.logging import get_logger
from aadap.core.tracing import TracingContext, create_span

logger = get_logger(__name__)


# ── Job Status ──────────────────────────────────────────────────────────

class JobStatus(StrEnum):
    """Databricks job lifecycle states."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ── Data Objects ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class JobSubmission:
    """Result of a job submission."""

    job_id: str
    task_id: uuid.UUID
    environment: str
    status: JobStatus = JobStatus.PENDING
    submitted_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True)
class JobResult:
    """Result of a completed job."""

    job_id: str
    status: JobStatus
    output: str | None = None
    error: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Exceptions ──────────────────────────────────────────────────────────


class DatabricksEnvironmentError(Exception):
    """Raised when environment validation fails (INV-05)."""

    def __init__(self, environment: str, reason: str) -> None:
        self.environment = environment
        super().__init__(
            f"INV-05: Environment '{environment}' validation failed: {reason}"
        )


# ── Abstract Base ───────────────────────────────────────────────────────


class BaseDatabricksClient(abc.ABC):
    """
    Abstract Databricks client.

    Concrete implementations connect to real Databricks workspace.
    Phase 7 provides the interface and a ``MockDatabricksClient``.
    """

    VALID_ENVIRONMENTS = {"SANDBOX", "PRODUCTION"}

    def _validate_environment(self, environment: str) -> None:
        """
        Validate the execution environment.

        INV-05: Ensures only known environments are accepted.
        """
        env = environment.upper()
        if env not in self.VALID_ENVIRONMENTS:
            raise DatabricksEnvironmentError(
                env, f"Must be one of {self.VALID_ENVIRONMENTS}"
            )

    @abc.abstractmethod
    async def submit_job(
        self,
        task_id: uuid.UUID,
        code: str,
        environment: str,
        correlation_id: str | None = None,
        language: str = "sql",
    ) -> JobSubmission:
        """
        Submit code for execution on Databricks.

        Parameters
        ----------
        task_id
            Unique task identifier.
        code
            Code to execute (SQL or Python).
        environment
            Execution environment (SANDBOX or PRODUCTION).
        correlation_id
            Optional correlation ID for tracing.
        language
            Language of the code: "sql" or "python". Default is "sql".
        """
        ...

    @abc.abstractmethod
    async def get_job_status(self, job_id: str) -> JobStatus:
        """Poll the current status of a submitted job."""
        ...

    @abc.abstractmethod
    async def get_job_output(self, job_id: str) -> JobResult:
        """Retrieve the output of a completed job."""
        ...


# ── Mock Implementation ────────────────────────────────────────────────


class MockDatabricksClient(BaseDatabricksClient):
    """
    Mock Databricks client for testing and development.

    Simulates job submission and execution with configurable outcomes.
    INV-05: Sandbox and production are tracked separately.
    """

    def __init__(
        self,
        default_output: str = "Mock execution output",
        default_status: JobStatus = JobStatus.SUCCESS,
        default_duration_ms: int = 1500,
    ) -> None:
        self._default_output = default_output
        self._default_status = default_status
        self._default_duration_ms = default_duration_ms
        self._jobs: dict[str, dict[str, Any]] = {}

    async def submit_job(
        self,
        task_id: uuid.UUID,
        code: str,
        environment: str,
        correlation_id: str | None = None,
        language: str = "sql",
    ) -> JobSubmission:
        """Submit a mock job. Validates environment per INV-05."""
        self._validate_environment(environment)

        job_id = f"mock-job-{uuid.uuid4().hex[:12]}"

        with create_span("databricks.submit", job_id=job_id) as span:
            ctx = TracingContext(correlation_id=correlation_id)
            trace_headers = ctx.inject_headers({})

            self._jobs[job_id] = {
                "task_id": task_id,
                "code": code,
                "environment": environment.upper(),
                "status": JobStatus.PENDING,
                "correlation_id": correlation_id,
                "trace_headers": trace_headers,
                "language": language,
            }

        logger.info(
            "databricks.job_submitted",
            job_id=job_id,
            task_id=str(task_id),
            environment=environment,
            correlation_id=correlation_id,
        )

        return JobSubmission(
            job_id=job_id,
            task_id=task_id,
            environment=environment.upper(),
        )

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Return mock job status. Transitions PENDING → configured status."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found.")

        # Simulate progression: PENDING → final status
        if job["status"] == JobStatus.PENDING:
            job["status"] = self._default_status

        return job["status"]

    async def get_job_output(self, job_id: str) -> JobResult:
        """Return mock job output."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Job {job_id} not found.")

        status = await self.get_job_status(job_id)

        if status == JobStatus.FAILED:
            return JobResult(
                job_id=job_id,
                status=status,
                error="Mock execution failure",
                duration_ms=self._default_duration_ms,
            )

        return JobResult(
            job_id=job_id,
            status=status,
            output=self._default_output,
            duration_ms=self._default_duration_ms,
            metadata={"environment": job["environment"]},
        )


# ── Real Databricks Implementation ───────────────────────────────────────


class DatabricksClient(BaseDatabricksClient):
    """
    Real Databricks client supporting both SQL and Python execution.

    SQL Execution:
        - Uses Statement Execution API with SQL Warehouse
        - Requires AADAP_DATABRICKS_WAREHOUSE_ID

    Python Execution:
        - Uses Command Execution API with Compute Cluster
        - Requires AADAP_DATABRICKS_CLUSTER_ID

    Authentication via CLI (already authenticated device).

    Required environment variables:
        - AADAP_DATABRICKS_HOST

    Optional (for SQL):
        - AADAP_DATABRICKS_WAREHOUSE_ID
        - AADAP_DATABRICKS_CATALOG
        - AADAP_DATABRICKS_SCHEMA

    Optional (for Python):
        - AADAP_DATABRICKS_CLUSTER_ID
    """

    _STATEMENT_STATE_MAP = {
        "PENDING": JobStatus.PENDING,
        "RUNNING": JobStatus.RUNNING,
        "SUCCEEDED": JobStatus.SUCCESS,
        "FAILED": JobStatus.FAILED,
        "CANCELED": JobStatus.CANCELLED,
        "CLOSED": JobStatus.SUCCESS,
    }

    _COMMAND_STATE_MAP = {
        "Running": JobStatus.RUNNING,
        "Finished": JobStatus.SUCCESS,
        "Error": JobStatus.FAILED,
        "Cancelled": JobStatus.CANCELLED,
    }

    def __init__(
        self,
        host: str,
        warehouse_id: str | None = None,
        cluster_id: str | None = None,
        catalog: str | None = None,
        schema: str | None = None,
    ) -> None:
        self._host = host
        self._warehouse_id = warehouse_id
        self._cluster_id = cluster_id
        self._catalog = catalog
        self._schema = schema
        self._workspace_client = None
        self._execution_cache: dict[str, dict[str, Any]] = {}

    @classmethod
    def from_settings(cls) -> "DatabricksClient":
        """Create a DatabricksClient from application settings."""
        settings = get_settings()
        if not settings.databricks_host:
            raise ValueError(
                "AADAP_DATABRICKS_HOST is required for DatabricksClient"
            )
        return cls(
            host=settings.databricks_host,
            warehouse_id=settings.databricks_warehouse_id,
            cluster_id=settings.databricks_cluster_id,
            catalog=settings.databricks_catalog,
            schema=settings.databricks_schema,
        )

    def _get_workspace_client(self):
        """Lazily initialize the Databricks WorkspaceClient."""
        if self._workspace_client is None:
            from databricks.sdk import WorkspaceClient
            self._workspace_client = WorkspaceClient(host=self._host)
        return self._workspace_client

    def _map_statement_state(self, state: str) -> JobStatus:
        """Map Databricks statement state to JobStatus enum."""
        return self._STATEMENT_STATE_MAP.get(state.upper(), JobStatus.PENDING)

    def _map_command_state(self, state: str) -> JobStatus:
        """Map Databricks command state to JobStatus enum."""
        return self._COMMAND_STATE_MAP.get(state, JobStatus.PENDING)

    async def submit_job(
        self,
        task_id: uuid.UUID,
        code: str,
        environment: str,
        correlation_id: str | None = None,
        language: str = "sql",
    ) -> JobSubmission:
        """
        Submit code for execution on Databricks.

        For SQL: Uses Statement Execution API with SQL Warehouse.
        For Python: Uses Command Execution API with Compute Cluster.
        """
        self._validate_environment(environment)

        if language.lower() == "python":
            return await self._submit_python(task_id, code, environment, correlation_id)
        else:
            return await self._submit_sql(task_id, code, environment, correlation_id)

    async def _submit_sql(
        self,
        task_id: uuid.UUID,
        code: str,
        environment: str,
        correlation_id: str | None = None,
    ) -> JobSubmission:
        """Submit SQL code via Statement Execution API."""
        if not self._warehouse_id:
            raise ValueError(
                "AADAP_DATABRICKS_WAREHOUSE_ID is required for SQL execution"
            )

        w = self._get_workspace_client()

        with create_span("databricks.sql_submit", task_id=str(task_id)) as span:
            ctx = TracingContext(correlation_id=correlation_id)
            trace_headers = ctx.inject_headers({})

            logger.info(
                "databricks.sql_submitting",
                task_id=str(task_id),
                environment=environment,
                warehouse_id=self._warehouse_id,
                correlation_id=correlation_id,
            )

            import asyncio

            wait_timeout = "50s"
            on_wait_timeout = "CANCEL"

            response = await asyncio.to_thread(
                w.statement_execution.execute_statement,
                statement=code,
                warehouse_id=self._warehouse_id,
                catalog=self._catalog,
                schema=self._schema,
                wait_timeout=wait_timeout,
                on_wait_timeout=on_wait_timeout,
            )

            statement_id = response.statement_id

            self._execution_cache[statement_id] = {
                "task_id": task_id,
                "environment": environment.upper(),
                "correlation_id": correlation_id,
                "trace_headers": trace_headers,
                "code": code,
                "language": "sql",
            }

            logger.info(
                "databricks.sql_submitted",
                statement_id=statement_id,
                task_id=str(task_id),
                environment=environment,
                correlation_id=correlation_id,
            )

            return JobSubmission(
                job_id=statement_id,
                task_id=task_id,
                environment=environment.upper(),
            )

    async def _submit_python(
        self,
        task_id: uuid.UUID,
        code: str,
        environment: str,
        correlation_id: str | None = None,
    ) -> JobSubmission:
        """Submit Python code via Command Execution API."""
        if not self._cluster_id:
            raise ValueError(
                "AADAP_DATABRICKS_CLUSTER_ID is required for Python execution"
            )

        w = self._get_workspace_client()

        with create_span("databricks.python_submit", task_id=str(task_id)) as span:
            ctx = TracingContext(correlation_id=correlation_id)
            trace_headers = ctx.inject_headers({})

            logger.info(
                "databricks.python_submitting",
                task_id=str(task_id),
                environment=environment,
                cluster_id=self._cluster_id,
                correlation_id=correlation_id,
            )

            import asyncio

            context_response = await asyncio.to_thread(
                w.command_execution.create_context,
                cluster_id=self._cluster_id,
                language="python",
            )

            context_id = context_response.id

            command_response = await asyncio.to_thread(
                w.command_execution.execute_command,
                cluster_id=self._cluster_id,
                context_id=context_id,
                language="python",
                command=code,
            )

            command_id = command_response.id

            self._execution_cache[command_id] = {
                "task_id": task_id,
                "environment": environment.upper(),
                "correlation_id": correlation_id,
                "trace_headers": trace_headers,
                "code": code,
                "language": "python",
                "context_id": context_id,
                "cluster_id": self._cluster_id,
            }

            logger.info(
                "databricks.python_submitted",
                command_id=command_id,
                context_id=context_id,
                task_id=str(task_id),
                environment=environment,
                correlation_id=correlation_id,
            )

            return JobSubmission(
                job_id=command_id,
                task_id=task_id,
                environment=environment.upper(),
            )

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Poll the current status of a submitted job."""
        execution_info = self._execution_cache.get(job_id, {})
        language = execution_info.get("language", "sql")

        if language == "python":
            return await self._get_python_status(job_id, execution_info)
        else:
            return await self._get_sql_status(job_id)

    async def _get_sql_status(self, statement_id: str) -> JobStatus:
        """Get status of a SQL statement."""
        w = self._get_workspace_client()

        import asyncio
        statement = await asyncio.to_thread(
            w.statement_execution.get_statement,
            statement_id=statement_id,
        )

        if statement.status:
            state = statement.status.state
            if state:
                return self._map_statement_state(state.value)

        return JobStatus.PENDING

    async def _get_python_status(self, command_id: str, execution_info: dict) -> JobStatus:
        """Get status of a Python command."""
        w = self._get_workspace_client()
        cluster_id = execution_info.get("cluster_id")
        context_id = execution_info.get("context_id")

        if not cluster_id or not context_id:
            return JobStatus.FAILED

        import asyncio
        try:
            command = await asyncio.to_thread(
                w.command_execution.get_command,
                cluster_id=cluster_id,
                context_id=context_id,
                command_id=command_id,
            )

            if command.status:
                return self._map_command_state(command.status.value)

            return JobStatus.PENDING
        except Exception as e:
            logger.warning(
                "databricks.python_status_error",
                command_id=command_id,
                error=str(e),
            )
            return JobStatus.FAILED

    async def get_job_output(self, job_id: str) -> JobResult:
        """Retrieve the output of a completed job."""
        execution_info = self._execution_cache.get(job_id, {})
        language = execution_info.get("language", "sql")

        if language == "python":
            return await self._get_python_output(job_id, execution_info)
        else:
            return await self._get_sql_output(job_id, execution_info)

    async def _get_sql_output(self, statement_id: str, execution_info: dict) -> JobResult:
        """Get output of a SQL statement."""
        w = self._get_workspace_client()
        status = await self._get_sql_status(statement_id)

        import asyncio
        statement = await asyncio.to_thread(
            w.statement_execution.get_statement,
            statement_id=statement_id,
        )

        duration_ms = None
        if statement.status:
            if statement.status.start_time and statement.status.end_time:
                start = statement.status.start_time
                end = statement.status.end_time
                duration_ms = int((end - start).total_seconds() * 1000)

        output = None
        error = None

        if status == JobStatus.FAILED:
            if statement.status and statement.status.error:
                error_msg = statement.status.error
                if hasattr(error_msg, 'message'):
                    error = error_msg.message
                else:
                    error = str(error_msg)
            else:
                error = "Databricks statement execution failed"
        else:
            if statement.result:
                result_data = statement.result
                if hasattr(result_data, 'data_array') and result_data.data_array:
                    output = self._format_result_data(
                        result_data.data_array,
                        result_data.row_count if hasattr(result_data, 'row_count') else None,
                    )
                elif hasattr(result_data, 'chunks') and result_data.chunks:
                    output = "[Results available via chunk links]"
                else:
                    output = "Statement executed successfully (no data returned)"

        return JobResult(
            job_id=statement_id,
            status=status,
            output=output,
            error=error,
            duration_ms=duration_ms,
            metadata={
                "environment": execution_info.get("environment"),
                "language": "sql",
                "warehouse_id": self._warehouse_id,
                "catalog": self._catalog,
                "schema": self._schema,
            },
        )

    async def _get_python_output(self, command_id: str, execution_info: dict) -> JobResult:
        """Get output of a Python command."""
        w = self._get_workspace_client()
        status = await self._get_python_status(command_id, execution_info)

        cluster_id = execution_info.get("cluster_id")
        context_id = execution_info.get("context_id")

        output = None
        error = None
        duration_ms = None

        if not cluster_id or not context_id:
            return JobResult(
                job_id=command_id,
                status=JobStatus.FAILED,
                error="Missing cluster_id or context_id",
                metadata={"language": "python"},
            )

        import asyncio
        try:
            command = await asyncio.to_thread(
                w.command_execution.get_command,
                cluster_id=cluster_id,
                context_id=context_id,
                command_id=command_id,
            )

            if command.results:
                results = command.results
                if hasattr(results, 'data') and results.data:
                    output = str(results.data)
                elif hasattr(results, 'result_type'):
                    if results.result_type and results.result_type.value == "text":
                        output = str(results.data) if hasattr(results, 'data') else "Execution completed"
                    elif results.result_type and results.result_type.value == "error":
                        error = str(results.cause) if hasattr(results, 'cause') else "Python execution error"
                        output = str(results.summary) if hasattr(results, 'summary') else None
                else:
                    output = "Python execution completed"
            elif status == JobStatus.FAILED:
                error = "Python command execution failed"

        except Exception as e:
            logger.warning(
                "databricks.python_output_error",
                command_id=command_id,
                error=str(e),
            )
            if status == JobStatus.SUCCESS:
                output = "Python execution completed (output unavailable)"
            else:
                error = str(e)

        return JobResult(
            job_id=command_id,
            status=status,
            output=output,
            error=error,
            duration_ms=duration_ms,
            metadata={
                "environment": execution_info.get("environment"),
                "language": "python",
                "cluster_id": cluster_id,
                "context_id": context_id,
            },
        )

    def _format_result_data(
        self,
        data_array: list[Any] | None,
        row_count: int | None,
    ) -> str:
        """Format statement result data as a readable string."""
        if not data_array:
            return "Statement executed successfully (empty result)"

        import json

        formatted_rows = []
        for row in data_array[:100]:
            if hasattr(row, '__iter__') and not isinstance(row, str):
                row_values = []
                for val in row:
                    if val is None:
                        row_values.append("NULL")
                    elif isinstance(val, (list, dict)):
                        row_values.append(json.dumps(val))
                    else:
                        row_values.append(str(val))
                formatted_rows.append(", ".join(row_values))
            else:
                formatted_rows.append(str(row))

        result = "\n".join(formatted_rows)

        if row_count and row_count > 100:
            result += f"\n... ({row_count - 100} more rows)"

        return result
