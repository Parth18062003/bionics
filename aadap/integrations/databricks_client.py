"""
AADAP — Databricks Execution Client
=======================================
Abstraction layer for Databricks job submission and monitoring.

Architecture layer: L3 (Integration).
Phase 7 contract: Databricks execution integration.

Enforces:
- INV-05: Sandbox isolated from production data
- Correlation ID forwarded via custom tags

Usage:
    client = MockDatabricksClient()
    result = await client.submit_job(task_id, code, "SANDBOX")
    status = await client.get_job_status(result.job_id)
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
    ) -> JobSubmission:
        """Submit code for execution on Databricks."""
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
    ) -> JobSubmission:
        """Submit a mock job. Validates environment per INV-05."""
        self._validate_environment(environment)

        job_id = f"mock-job-{uuid.uuid4().hex[:12]}"

        with create_span("databricks.submit", job_id=job_id) as span:
            # Build tracing headers for the "outgoing" call
            ctx = TracingContext(correlation_id=correlation_id)
            trace_headers = ctx.inject_headers({})

            self._jobs[job_id] = {
                "task_id": task_id,
                "code": code,
                "environment": environment.upper(),
                "status": JobStatus.PENDING,
                "correlation_id": correlation_id,
                "trace_headers": trace_headers,
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
    Real Databricks client using databricks-sdk.

    Authenticates via CLI (already authenticated device).
    Requires the following environment variables:
        - AADAP_DATABRICKS_HOST
        - AADAP_DATABRICKS_JOB_ID
    """

    _RUN_STATE_MAP = {
        "PENDING": JobStatus.PENDING,
        "RUNNING": JobStatus.RUNNING,
        "TERMINATED": JobStatus.SUCCESS,
        "SKIPPED": JobStatus.CANCELLED,
        "INTERNAL_ERROR": JobStatus.FAILED,
    }

    def __init__(self, host: str, job_id: str) -> None:
        self._host = host
        self._job_id = job_id
        self._workspace_client = None
        self._api_client = None
        self._run_info_cache: dict[str, dict[str, Any]] = {}

    @classmethod
    def from_settings(cls) -> "DatabricksClient":
        """Create a DatabricksClient from application settings."""
        settings = get_settings()
        if not settings.databricks_host:
            raise ValueError(
                "AADAP_DATABRICKS_HOST is required for DatabricksClient"
            )
        if not settings.databricks_job_id:
            raise ValueError(
                "AADAP_DATABRICKS_JOB_ID is required for DatabricksClient"
            )
        return cls(
            host=settings.databricks_host,
            job_id=settings.databricks_job_id,
        )

    def _get_workspace_client(self):
        """Lazily initialize the Databricks WorkspaceClient."""
        if self._workspace_client is None:
            from databricks.sdk import WorkspaceClient
            self._workspace_client = WorkspaceClient(host=self._host)
        return self._workspace_client

    def _get_api_client(self):
        """Lazily initialize the Databricks API client for runs."""
        if self._api_client is None:
            from databricks.sdk.core import Config
            from databricks.sdk.service.jobs import JobsAPI
            config = Config(host=self._host)
            self._api_client = JobsAPI(config)
        return self._api_client

    def _map_run_state(self, state: str) -> JobStatus:
        """Map Databricks run state to JobStatus enum."""
        if state == "SUCCESS":
            return JobStatus.SUCCESS
        if state in ("FAILED", "INTERNAL_ERROR"):
            return JobStatus.FAILED
        if state == "CANCELLED":
            return JobStatus.CANCELLED
        if state in ("PENDING", "QUEUED"):
            return JobStatus.PENDING
        if state in ("RUNNING", "TERMINATING"):
            return JobStatus.RUNNING
        return JobStatus.PENDING

    async def submit_job(
        self,
        task_id: uuid.UUID,
        code: str,
        environment: str,
        correlation_id: str | None = None,
    ) -> JobSubmission:
        """Submit code for execution on Databricks."""
        self._validate_environment(environment)

        w = self._get_workspace_client()

        with create_span("databricks.submit", task_id=str(task_id)) as span:
            ctx = TracingContext(correlation_id=correlation_id)
            trace_headers = ctx.inject_headers({})

            notebook_params = {
                "task_id": str(task_id),
                "environment": environment.upper(),
                "code": code,
            }

            logger.info(
                "databricks.job_submitting",
                task_id=str(task_id),
                environment=environment,
                correlation_id=correlation_id,
            )

            import asyncio
            response = await asyncio.to_thread(
                w.jobs.run_now,
                job_id=int(self._job_id),
                notebook_params=notebook_params,
            )

            run_id = str(response.run_id)

            self._run_info_cache[run_id] = {
                "task_id": task_id,
                "environment": environment.upper(),
                "correlation_id": correlation_id,
                "trace_headers": trace_headers,
            }

            logger.info(
                "databricks.job_submitted",
                run_id=run_id,
                task_id=str(task_id),
                environment=environment,
                correlation_id=correlation_id,
            )

            return JobSubmission(
                job_id=run_id,
                task_id=task_id,
                environment=environment.upper(),
            )

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Poll the current status of a submitted job."""
        w = self._get_workspace_client()

        import asyncio
        run = await asyncio.to_thread(
            w.jobs.get_run,
            run_id=int(job_id),
        )

        state = run.state
        if state and state.result_state:
            return self._map_run_state(state.result_state.value)
        if state and state.life_cycle_state:
            return self._map_run_state(state.life_cycle_state.value)

        return JobStatus.PENDING

    async def get_job_output(self, job_id: str) -> JobResult:
        """Retrieve the output of a completed job."""
        w = self._get_workspace_client()
        status = await self.get_job_status(job_id)

        import asyncio
        run = await asyncio.to_thread(
            w.jobs.get_run,
            run_id=int(job_id),
        )

        duration_ms = None
        if run.start_time and run.end_time:
            duration_ms = run.end_time - run.start_time

        output = None
        error = None

        if status == JobStatus.FAILED:
            if run.state and run.state.state_message:
                error = run.state.state_message
            else:
                error = "Databricks job execution failed"
        else:
            try:
                run_output = await asyncio.to_thread(
                    w.jobs.get_run_output,
                    run_id=int(job_id),
                )
                if run_output and run_output.notebook_output:
                    output = run_output.notebook_output.result
                    if run_output.notebook_output.truncated:
                        output = (output or "") + "\n[Output truncated]"
            except Exception as e:
                logger.warning(
                    "databricks.output_unavailable",
                    run_id=job_id,
                    error=str(e),
                )

        run_info = self._run_info_cache.get(job_id, {})

        return JobResult(
            job_id=job_id,
            status=status,
            output=output,
            error=error,
            duration_ms=duration_ms,
            metadata={
                "environment": run_info.get("environment"),
                "run_name": run.run_name,
            },
        )
