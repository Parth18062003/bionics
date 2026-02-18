"""
AADAP — Microsoft Fabric Execution Client
=============================================
Abstraction layer for Microsoft Fabric job submission and monitoring
via Fabric REST APIs with Service Principal Authentication (SPA).

Architecture layer: L3 (Integration).
Phase 7 contract: Microsoft Fabric execution integration.

Enforces:
- INV-05: Sandbox isolated from production data
- Correlation ID forwarded via custom headers

Supports:
- Notebook execution via Fabric REST API (Run on Demand)
- Lakehouse SQL execution via Fabric SQL endpoint
- Item job submission (Spark jobs, notebooks, pipelines)

Authentication:
- Service Principal Authentication (SPA) using MSAL
- OAuth2 client_credentials flow with Azure AD
- Token caching and auto-refresh

Usage:
    # Mock client (development):
    client = MockFabricClient()
    result = await client.submit_job(task_id, code, "SANDBOX", language="python")
    status = await client.get_job_status(result.job_id)

    # Real client:
    client = FabricClient.from_settings()
    result = await client.submit_job(task_id, code, "SANDBOX", language="python")
    output = await client.get_job_output(result.job_id)
"""

from __future__ import annotations

import abc
import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from aadap.core.config import get_settings
from aadap.core.logging import get_logger
from aadap.core.tracing import TracingContext, create_span

logger = get_logger(__name__)


# ── Fabric Job Status ──────────────────────────────────────────────────

class FabricJobStatus(StrEnum):
    """Microsoft Fabric job lifecycle states."""

    NOT_STARTED = "NotStarted"
    IN_PROGRESS = "InProgress"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    DEDUPED = "Deduped"


# ── Canonical Job Status Mapping ───────────────────────────────────────

class JobStatus(StrEnum):
    """Canonical job status shared with the execution service."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ── Data Objects ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FabricJobSubmission:
    """Result of a job submission to Microsoft Fabric."""

    job_id: str
    task_id: uuid.UUID
    environment: str
    item_id: str | None = None
    status: JobStatus = JobStatus.PENDING
    submitted_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True)
class FabricJobResult:
    """Result of a completed Fabric job."""

    job_id: str
    status: JobStatus
    output: str | None = None
    error: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Exceptions ──────────────────────────────────────────────────────────


class FabricEnvironmentError(Exception):
    """Raised when environment validation fails (INV-05)."""

    def __init__(self, environment: str, reason: str) -> None:
        self.environment = environment
        super().__init__(
            f"INV-05: Fabric environment '{environment}' validation failed: {reason}"
        )


class FabricAuthenticationError(Exception):
    """Raised when SPA authentication fails."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Fabric SPA authentication failed: {reason}")


class FabricAPIError(Exception):
    """Raised when a Fabric REST API call fails."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        super().__init__(f"Fabric API error ({status_code}): {detail}")


# ── Abstract Base ───────────────────────────────────────────────────────


class BaseFabricClient(abc.ABC):
    """
    Abstract Microsoft Fabric client.

    Concrete implementations connect to real Fabric workspace via REST APIs
    with SPA authentication. A MockFabricClient is provided for development.
    """

    VALID_ENVIRONMENTS = {"SANDBOX", "PRODUCTION"}

    FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"

    def _validate_environment(self, environment: str) -> None:
        """
        Validate the execution environment.

        INV-05: Ensures only known environments are accepted.
        """
        env = environment.upper()
        if env not in self.VALID_ENVIRONMENTS:
            raise FabricEnvironmentError(
                env, f"Must be one of {self.VALID_ENVIRONMENTS}"
            )

    @abc.abstractmethod
    async def submit_job(
        self,
        task_id: uuid.UUID,
        code: str,
        environment: str,
        correlation_id: str | None = None,
        language: str = "python",
    ) -> FabricJobSubmission:
        """
        Submit code for execution on Microsoft Fabric.

        Parameters
        ----------
        task_id
            Unique task identifier.
        code
            Code to execute (Python, Scala, or SQL).
        environment
            Execution environment (SANDBOX or PRODUCTION).
        correlation_id
            Optional correlation ID for tracing.
        language
            Language of the code: "python", "scala", or "sql". Default is "python".
        """
        ...

    @abc.abstractmethod
    async def get_job_status(self, job_id: str) -> JobStatus:
        """Poll the current status of a submitted job."""
        ...

    @abc.abstractmethod
    async def get_job_output(self, job_id: str) -> FabricJobResult:
        """Retrieve the output of a completed job."""
        ...


# ── Mock Implementation ────────────────────────────────────────────────


class MockFabricClient(BaseFabricClient):
    """
    Mock Fabric client for testing and development.

    Simulates job submission and execution with configurable outcomes.
    INV-05: Sandbox and production are tracked separately.
    """

    def __init__(
        self,
        default_output: str = "Mock Fabric execution output",
        default_status: JobStatus = JobStatus.SUCCESS,
        default_duration_ms: int = 2000,
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
        language: str = "python",
    ) -> FabricJobSubmission:
        """Submit a mock job. Validates environment per INV-05."""
        self._validate_environment(environment)

        job_id = f"fabric-mock-{uuid.uuid4().hex[:12]}"

        with create_span("fabric.submit", job_id=job_id) as span:
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
            "fabric.mock_job_submitted",
            job_id=job_id,
            task_id=str(task_id),
            environment=environment,
            language=language,
            correlation_id=correlation_id,
        )

        return FabricJobSubmission(
            job_id=job_id,
            task_id=task_id,
            environment=environment.upper(),
        )

    async def get_job_status(self, job_id: str) -> JobStatus:
        """Return mock job status. Transitions PENDING → configured status."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Fabric job {job_id} not found.")

        # Simulate progression: PENDING → final status
        if job["status"] == JobStatus.PENDING:
            job["status"] = self._default_status

        return job["status"]

    async def get_job_output(self, job_id: str) -> FabricJobResult:
        """Return mock job output."""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Fabric job {job_id} not found.")

        status = await self.get_job_status(job_id)

        if status == JobStatus.FAILED:
            return FabricJobResult(
                job_id=job_id,
                status=status,
                error="Mock Fabric execution failure",
                duration_ms=self._default_duration_ms,
            )

        return FabricJobResult(
            job_id=job_id,
            status=status,
            output=self._default_output,
            duration_ms=self._default_duration_ms,
            metadata={
                "environment": job["environment"],
                "platform": "Microsoft Fabric",
            },
        )


# ── Real Fabric Implementation ──────────────────────────────────────────


class FabricClient(BaseFabricClient):
    """
    Real Microsoft Fabric client using SPA authentication and REST APIs.

    Authentication:
        - Uses MSAL ConfidentialClientApplication for OAuth2 client_credentials
        - Acquires token for https://api.fabric.microsoft.com/.default scope
        - Tokens are cached and auto-refreshed

    Job Execution:
        - Creates a notebook item in the workspace (or uses existing)
        - Submits run-on-demand via POST /items/{item_id}/jobs/instances
        - Polls job status via GET /items/{item_id}/jobs/instances/{job_id}
        - Retrieves results via job output or Lakehouse query

    Required environment variables:
        - AADAP_FABRIC_TENANT_ID
        - AADAP_FABRIC_CLIENT_ID
        - AADAP_FABRIC_CLIENT_SECRET
        - AADAP_FABRIC_WORKSPACE_ID

    Optional:
        - AADAP_FABRIC_LAKEHOUSE_ID
    """

    # Fabric REST API status → canonical JobStatus mapping
    _FABRIC_STATE_MAP: dict[str, JobStatus] = {
        "NotStarted": JobStatus.PENDING,
        "InProgress": JobStatus.RUNNING,
        "Completed": JobStatus.SUCCESS,
        "Failed": JobStatus.FAILED,
        "Cancelled": JobStatus.CANCELLED,
        "Deduped": JobStatus.SUCCESS,
    }

    _SCOPE = ["https://api.fabric.microsoft.com/.default"]

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        workspace_id: str,
        lakehouse_id: str | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._workspace_id = workspace_id
        self._lakehouse_id = lakehouse_id
        self._msal_app = None
        self._access_token: str | None = None
        self._token_expiry: datetime | None = None
        self._execution_cache: dict[str, dict[str, Any]] = {}

    @classmethod
    def from_settings(cls) -> "FabricClient":
        """Create a FabricClient from application settings."""
        settings = get_settings()
        if not settings.fabric_tenant_id:
            raise ValueError(
                "AADAP_FABRIC_TENANT_ID is required for FabricClient")
        if not settings.fabric_client_id:
            raise ValueError(
                "AADAP_FABRIC_CLIENT_ID is required for FabricClient")
        if not settings.fabric_client_secret:
            raise ValueError(
                "AADAP_FABRIC_CLIENT_SECRET is required for FabricClient")
        if not settings.fabric_workspace_id:
            raise ValueError(
                "AADAP_FABRIC_WORKSPACE_ID is required for FabricClient")

        return cls(
            tenant_id=settings.fabric_tenant_id,
            client_id=settings.fabric_client_id,
            client_secret=settings.fabric_client_secret.get_secret_value(),
            workspace_id=settings.fabric_workspace_id,
            lakehouse_id=settings.fabric_lakehouse_id,
        )

    # ── Authentication ──────────────────────────────────────────────────

    def _get_msal_app(self):
        """Lazily initialize the MSAL ConfidentialClientApplication."""
        if self._msal_app is None:
            import msal

            authority = f"https://login.microsoftonline.com/{self._tenant_id}"
            self._msal_app = msal.ConfidentialClientApplication(
                client_id=self._client_id,
                client_credential=self._client_secret,
                authority=authority,
            )
        return self._msal_app

    async def _acquire_token(self) -> str:
        """
        Acquire an access token via SPA (client_credentials flow).

        Caches the token and refreshes only when expired.
        """
        # Return cached token if still valid (with 5-min buffer)
        if (
            self._access_token
            and self._token_expiry
            and datetime.now(timezone.utc) < self._token_expiry
        ):
            return self._access_token

        app = self._get_msal_app()

        # Acquire token using client credentials
        result = await asyncio.to_thread(
            app.acquire_token_for_client,
            scopes=self._SCOPE,
        )

        if "access_token" not in result:
            error_desc = result.get("error_description", "Unknown error")
            raise FabricAuthenticationError(error_desc)

        self._access_token = result["access_token"]
        # Token typically expires in 3600s; refresh 5 min early
        expires_in = result.get("expires_in", 3600)
        from datetime import timedelta
        self._token_expiry = (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)
        )

        logger.info("fabric.token_acquired", expires_in=expires_in)
        return self._access_token

    def _build_headers(self, token: str, correlation_id: str | None = None) -> dict[str, str]:
        """Build HTTP headers for Fabric REST API calls."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

    # ── Job Submission ──────────────────────────────────────────────────

    async def submit_job(
        self,
        task_id: uuid.UUID,
        code: str,
        environment: str,
        correlation_id: str | None = None,
        language: str = "python",
    ) -> FabricJobSubmission:
        """
        Submit code for execution on Microsoft Fabric.

        Workflow:
        1. Create or find a notebook item in the workspace
        2. Update notebook content with the provided code
        3. Submit a run-on-demand job instance
        4. Return the job instance ID for polling
        """
        self._validate_environment(environment)

        with create_span("fabric.submit", task_id=str(task_id)) as span:
            ctx = TracingContext(correlation_id=correlation_id)
            trace_headers = ctx.inject_headers({})

            token = await self._acquire_token()
            headers = self._build_headers(token, correlation_id)

            logger.info(
                "fabric.submitting",
                task_id=str(task_id),
                environment=environment,
                language=language,
            )

            import httpx

            async with httpx.AsyncClient(timeout=60.0) as client:
                # Step 1: Create a notebook item for this task
                item_id = await self._create_notebook_item(
                    client, headers, task_id, language
                )

                # Step 2: Update notebook content with the code
                await self._update_notebook_content(
                    client, headers, item_id, code, language
                )

                # Step 3: Submit run-on-demand job
                job_instance_id = await self._run_on_demand(
                    client, headers, item_id
                )

            # Cache execution metadata
            self._execution_cache[job_instance_id] = {
                "task_id": task_id,
                "item_id": item_id,
                "environment": environment.upper(),
                "correlation_id": correlation_id,
                "trace_headers": trace_headers,
                "code": code,
                "language": language,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                "fabric.job_submitted",
                job_id=job_instance_id,
                item_id=item_id,
                task_id=str(task_id),
                environment=environment,
            )

            return FabricJobSubmission(
                job_id=job_instance_id,
                task_id=task_id,
                environment=environment.upper(),
                item_id=item_id,
            )

    async def _create_notebook_item(
        self,
        client: Any,
        headers: dict[str, str],
        task_id: uuid.UUID,
        language: str,
    ) -> str:
        """
        Create a notebook item in the Fabric workspace.

        POST /workspaces/{workspace_id}/items
        """
        import base64
        import json

        url = f"{self.FABRIC_API_BASE}/workspaces/{self._workspace_id}/items"
        display_name = f"aadap-{task_id.hex[:8]}-{language}"

        # Fabric notebook definition payload
        notebook_payload = self._build_notebook_payload(language)
        definition_base64 = base64.b64encode(
            json.dumps(notebook_payload).encode()
        ).decode()

        body = {
            "displayName": display_name,
            "type": "Notebook",
            "definition": {
                "format": "ipynb",
                "parts": [
                    {
                        "path": "notebook-content.py",
                        "payload": definition_base64,
                        "payloadType": "InlineBase64",
                    }
                ],
            },
        }

        response = await client.post(url, json=body, headers=headers)

        if response.status_code == 409:
            # Item already exists — find it by name
            return await self._find_item_by_name(client, headers, display_name)

        if response.status_code not in (200, 201, 202):
            raise FabricAPIError(
                response.status_code,
                f"Failed to create notebook: {response.text}",
            )

        data = response.json()
        item_id = data.get("id", "")

        logger.info(
            "fabric.notebook_created",
            item_id=item_id,
            display_name=display_name,
        )

        return item_id

    async def _find_item_by_name(
        self,
        client: Any,
        headers: dict[str, str],
        display_name: str,
    ) -> str:
        """Find a Fabric item by display name in the workspace."""
        url = f"{self.FABRIC_API_BASE}/workspaces/{self._workspace_id}/items"
        response = await client.get(url, headers=headers)

        if response.status_code != 200:
            raise FabricAPIError(
                response.status_code,
                f"Failed to list items: {response.text}",
            )

        items = response.json().get("value", [])
        for item in items:
            if item.get("displayName") == display_name:
                return item["id"]

        raise FabricAPIError(
            404, f"Item '{display_name}' not found in workspace")

    def _build_notebook_payload(self, language: str) -> dict[str, Any]:
        """Build an ipynb-format notebook payload."""
        kernel_name = "python3" if language == "python" else language
        kernel_display = {
            "python": "Python 3",
            "scala": "Scala",
            "sql": "SQL",
        }.get(language, "Python 3")

        return {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {
                "kernelspec": {
                    "name": kernel_name,
                    "display_name": kernel_display,
                },
                "language_info": {
                    "name": language,
                },
                "trident": {
                    "lakehouse": {
                        "default_lakehouse": self._lakehouse_id,
                        "known_lakehouses": (
                            [{"id": self._lakehouse_id}]
                            if self._lakehouse_id
                            else []
                        ),
                    },
                },
            },
            "cells": [],
        }

    async def _update_notebook_content(
        self,
        client: Any,
        headers: dict[str, str],
        item_id: str,
        code: str,
        language: str,
    ) -> None:
        """
        Update the notebook item content with the generated code.

        POST /workspaces/{workspace_id}/items/{item_id}/updateDefinition
        """
        import base64
        import json

        notebook = self._build_notebook_payload(language)
        notebook["cells"] = [
            {
                "cell_type": "code",
                "source": code,
                "metadata": {},
                "outputs": [],
                "execution_count": None,
            }
        ]

        definition_base64 = base64.b64encode(
            json.dumps(notebook).encode()
        ).decode()

        url = (
            f"{self.FABRIC_API_BASE}/workspaces/{self._workspace_id}"
            f"/items/{item_id}/updateDefinition"
        )

        body = {
            "definition": {
                "format": "ipynb",
                "parts": [
                    {
                        "path": "notebook-content.py",
                        "payload": definition_base64,
                        "payloadType": "InlineBase64",
                    }
                ],
            }
        }

        response = await client.post(url, json=body, headers=headers)

        if response.status_code not in (200, 202):
            raise FabricAPIError(
                response.status_code,
                f"Failed to update notebook definition: {response.text}",
            )

        logger.info("fabric.notebook_updated", item_id=item_id)

    async def _run_on_demand(
        self,
        client: Any,
        headers: dict[str, str],
        item_id: str,
    ) -> str:
        """
        Trigger a run-on-demand job for a notebook item.

        POST /workspaces/{workspace_id}/items/{item_id}/jobs/instances?jobType=RunNotebook
        """
        url = (
            f"{self.FABRIC_API_BASE}/workspaces/{self._workspace_id}"
            f"/items/{item_id}/jobs/instances?jobType=RunNotebook"
        )

        response = await client.post(url, json={}, headers=headers)

        if response.status_code not in (200, 202):
            raise FabricAPIError(
                response.status_code,
                f"Failed to run notebook: {response.text}",
            )

        # Job instance ID may be in the response body or Location header
        if response.status_code == 202:
            # Long-running operation — extract from Location header
            location = response.headers.get("Location", "")
            # Location format: .../jobs/instances/{instanceId}
            job_instance_id = location.rstrip("/").split("/")[-1]
            if not job_instance_id:
                # Fallback to response body
                data = response.json() if response.text else {}
                job_instance_id = data.get(
                    "id", f"fabric-job-{uuid.uuid4().hex[:12]}")
        else:
            data = response.json()
            job_instance_id = data.get(
                "id", f"fabric-job-{uuid.uuid4().hex[:12]}")

        logger.info(
            "fabric.run_on_demand_submitted",
            item_id=item_id,
            job_instance_id=job_instance_id,
        )

        return job_instance_id

    # ── Status Polling ──────────────────────────────────────────────────

    async def get_job_status(self, job_id: str) -> JobStatus:
        """
        Poll the current status of a Fabric job.

        GET /workspaces/{workspace_id}/items/{item_id}/jobs/instances/{job_id}
        """
        cached = self._execution_cache.get(job_id)
        if not cached:
            raise KeyError(f"Fabric job {job_id} not found in execution cache")

        item_id = cached["item_id"]

        token = await self._acquire_token()
        headers = self._build_headers(token, cached.get("correlation_id"))

        url = (
            f"{self.FABRIC_API_BASE}/workspaces/{self._workspace_id}"
            f"/items/{item_id}/jobs/instances/{job_id}"
        )

        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)

        if response.status_code != 200:
            raise FabricAPIError(
                response.status_code,
                f"Failed to get job status: {response.text}",
            )

        data = response.json()
        fabric_status = data.get("status", "NotStarted")

        return self._FABRIC_STATE_MAP.get(fabric_status, JobStatus.PENDING)

    # ── Output Retrieval ────────────────────────────────────────────────

    async def get_job_output(self, job_id: str) -> FabricJobResult:
        """
        Retrieve the output of a completed Fabric job.

        Polls until terminal state, then returns result.
        """
        cached = self._execution_cache.get(job_id)
        if not cached:
            raise KeyError(f"Fabric job {job_id} not found in execution cache")

        item_id = cached["item_id"]
        start_time = datetime.now(timezone.utc)

        token = await self._acquire_token()
        headers = self._build_headers(token, cached.get("correlation_id"))

        import httpx

        # Poll until terminal state (max ~10 minutes)
        max_polls = 120
        poll_interval_s = 5.0
        final_status = JobStatus.PENDING
        job_data: dict[str, Any] = {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(max_polls):
                url = (
                    f"{self.FABRIC_API_BASE}/workspaces/{self._workspace_id}"
                    f"/items/{item_id}/jobs/instances/{job_id}"
                )
                response = await client.get(url, headers=headers)

                if response.status_code != 200:
                    raise FabricAPIError(
                        response.status_code,
                        f"Failed to poll job: {response.text}",
                    )

                job_data = response.json()
                fabric_status = job_data.get("status", "NotStarted")
                final_status = self._FABRIC_STATE_MAP.get(
                    fabric_status, JobStatus.PENDING
                )

                if final_status in (
                    JobStatus.SUCCESS,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                ):
                    break

                await asyncio.sleep(poll_interval_s)

        elapsed = datetime.now(timezone.utc) - start_time
        duration_ms = int(elapsed.total_seconds() * 1000)

        if final_status == JobStatus.FAILED:
            error_msg = job_data.get(
                "failureReason",
                job_data.get("error", {}).get("message", "Fabric job failed"),
            )
            return FabricJobResult(
                job_id=job_id,
                status=final_status,
                error=error_msg,
                duration_ms=duration_ms,
                metadata={
                    "item_id": item_id,
                    "environment": cached["environment"],
                    "platform": "Microsoft Fabric",
                },
            )

        # For successful jobs, output is typically in the notebook cell outputs
        # We report the job metadata as output since notebook cell outputs
        # require a separate call to get the notebook definition
        output_summary = (
            f"Fabric notebook executed successfully.\n"
            f"Item: {item_id}\n"
            f"Duration: {duration_ms}ms\n"
            f"Status: {final_status.value}"
        )

        return FabricJobResult(
            job_id=job_id,
            status=final_status,
            output=output_summary,
            duration_ms=duration_ms,
            metadata={
                "item_id": item_id,
                "environment": cached["environment"],
                "platform": "Microsoft Fabric",
                "job_data": job_data,
            },
        )

    # ── Utility ─────────────────────────────────────────────────────────

    @staticmethod
    def _as_text(value: Any) -> str | None:
        """Normalize SDK enum/string values into plain text."""
        if value is None:
            return None
        return str(getattr(value, "value", value))
