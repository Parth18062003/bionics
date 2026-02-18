"""
AADAP — Fabric Client Tests
================================
Tests for Microsoft Fabric execution client.

Validates:
- MockFabricClient job submission and retrieval
- INV-05 environment validation (sandbox isolation)
- Correlation ID forwarding
- Job lifecycle (PENDING → SUCCESS/FAILED)
- FabricClient.from_settings() factory
- FabricJobStatus mapping
"""

from __future__ import annotations

import uuid

import pytest

from aadap.integrations.fabric_client import (
    BaseFabricClient,
    FabricAPIError,
    FabricAuthenticationError,
    FabricClient,
    FabricEnvironmentError,
    FabricJobResult,
    FabricJobStatus,
    FabricJobSubmission,
    JobStatus,
    MockFabricClient,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    """Fresh MockFabricClient for each test."""
    return MockFabricClient()


@pytest.fixture
def failing_client():
    """MockFabricClient that simulates failures."""
    return MockFabricClient(default_status=JobStatus.FAILED)


# ── Job Submission Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_job_sandbox(mock_client):
    """Submit a job in SANDBOX environment."""
    task_id = uuid.uuid4()
    result = await mock_client.submit_job(
        task_id=task_id,
        code="print('hello fabric')",
        environment="SANDBOX",
        language="python",
    )

    assert isinstance(result, FabricJobSubmission)
    assert result.task_id == task_id
    assert result.environment == "SANDBOX"
    assert result.status == JobStatus.PENDING
    assert result.job_id.startswith("fabric-mock-")


@pytest.mark.asyncio
async def test_submit_job_production(mock_client):
    """Submit a job in PRODUCTION environment."""
    task_id = uuid.uuid4()
    result = await mock_client.submit_job(
        task_id=task_id,
        code="spark.read.table('sales')",
        environment="PRODUCTION",
        language="python",
    )

    assert result.environment == "PRODUCTION"


@pytest.mark.asyncio
async def test_submit_job_with_correlation_id(mock_client):
    """Correlation ID should be forwarded to the job."""
    task_id = uuid.uuid4()
    result = await mock_client.submit_job(
        task_id=task_id,
        code="SELECT 1",
        environment="SANDBOX",
        correlation_id="corr-fabric-123",
        language="sql",
    )

    assert result.job_id is not None


@pytest.mark.asyncio
async def test_submit_job_scala(mock_client):
    """Submit a Scala job."""
    task_id = uuid.uuid4()
    result = await mock_client.submit_job(
        task_id=task_id,
        code='val df = spark.read.table("events")',
        environment="SANDBOX",
        language="scala",
    )

    assert result.task_id == task_id
    assert result.status == JobStatus.PENDING


# ── Environment Validation Tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_environment_rejected(mock_client):
    """INV-05: Invalid environments must raise FabricEnvironmentError."""
    with pytest.raises(FabricEnvironmentError):
        await mock_client.submit_job(
            task_id=uuid.uuid4(),
            code="SELECT 1",
            environment="INVALID",
        )


@pytest.mark.asyncio
async def test_environment_case_insensitive(mock_client):
    """Environment names should be case-insensitive."""
    result = await mock_client.submit_job(
        task_id=uuid.uuid4(),
        code="SELECT 1",
        environment="sandbox",
        language="sql",
    )
    assert result.environment == "SANDBOX"


# ── Job Status Tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_job_status_transitions_to_success(mock_client):
    """Job should transition from PENDING → SUCCESS."""
    task_id = uuid.uuid4()
    submission = await mock_client.submit_job(
        task_id=task_id,
        code="SELECT 1",
        environment="SANDBOX",
    )

    status = await mock_client.get_job_status(submission.job_id)
    assert status == JobStatus.SUCCESS


@pytest.mark.asyncio
async def test_job_status_transitions_to_failed(failing_client):
    """Failing client should transition to FAILED."""
    task_id = uuid.uuid4()
    submission = await failing_client.submit_job(
        task_id=task_id,
        code="bad code",
        environment="SANDBOX",
    )

    status = await failing_client.get_job_status(submission.job_id)
    assert status == JobStatus.FAILED


@pytest.mark.asyncio
async def test_job_status_unknown_job(mock_client):
    """Polling a non-existent job should raise KeyError."""
    with pytest.raises(KeyError):
        await mock_client.get_job_status("nonexistent-job")


# ── Job Output Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_job_output_success(mock_client):
    """Successful job should return output."""
    task_id = uuid.uuid4()
    submission = await mock_client.submit_job(
        task_id=task_id,
        code="spark.sql('SELECT 1')",
        environment="SANDBOX",
        language="python",
    )

    result = await mock_client.get_job_output(submission.job_id)

    assert isinstance(result, FabricJobResult)
    assert result.status == JobStatus.SUCCESS
    assert result.output == "Mock Fabric execution output"
    assert result.error is None
    assert result.duration_ms == 2000
    assert result.metadata.get("platform") == "Microsoft Fabric"


@pytest.mark.asyncio
async def test_get_job_output_failure(failing_client):
    """Failed job should return error details."""
    task_id = uuid.uuid4()
    submission = await failing_client.submit_job(
        task_id=task_id,
        code="bad code",
        environment="SANDBOX",
    )

    result = await failing_client.get_job_output(submission.job_id)

    assert result.status == JobStatus.FAILED
    assert result.error is not None
    assert result.output is None


@pytest.mark.asyncio
async def test_get_job_output_unknown_job(mock_client):
    """Retrieving output of a non-existent job should raise KeyError."""
    with pytest.raises(KeyError):
        await mock_client.get_job_output("nonexistent-job")


# ── Custom Configuration Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_custom_output(mock_client):
    """Custom default output should be returned."""
    custom = MockFabricClient(default_output="Custom Fabric result")
    submission = await custom.submit_job(
        task_id=uuid.uuid4(),
        code="SELECT 1",
        environment="SANDBOX",
    )
    result = await custom.get_job_output(submission.job_id)
    assert result.output == "Custom Fabric result"


@pytest.mark.asyncio
async def test_custom_duration(mock_client):
    """Custom default duration should be returned."""
    custom = MockFabricClient(default_duration_ms=5000)
    submission = await custom.submit_job(
        task_id=uuid.uuid4(),
        code="SELECT 1",
        environment="SANDBOX",
    )
    result = await custom.get_job_output(submission.job_id)
    assert result.duration_ms == 5000


# ── Data Object Tests ──────────────────────────────────────────────────


def test_fabric_job_submission_frozen():
    """FabricJobSubmission should be immutable."""
    s = FabricJobSubmission(
        job_id="test-123",
        task_id=uuid.uuid4(),
        environment="SANDBOX",
    )
    with pytest.raises(AttributeError):
        s.job_id = "changed"  # type: ignore[misc]


def test_fabric_job_result_frozen():
    """FabricJobResult should be immutable."""
    r = FabricJobResult(
        job_id="test-456",
        status=JobStatus.SUCCESS,
        output="test output",
    )
    with pytest.raises(AttributeError):
        r.output = "changed"  # type: ignore[misc]


# ── FabricJobStatus Enum Tests ─────────────────────────────────────────


def test_fabric_job_status_values():
    """FabricJobStatus should have expected values."""
    assert FabricJobStatus.NOT_STARTED == "NotStarted"
    assert FabricJobStatus.IN_PROGRESS == "InProgress"
    assert FabricJobStatus.COMPLETED == "Completed"
    assert FabricJobStatus.FAILED == "Failed"
    assert FabricJobStatus.CANCELLED == "Cancelled"


def test_canonical_job_status_values():
    """Canonical JobStatus should match expected values."""
    assert JobStatus.PENDING == "PENDING"
    assert JobStatus.RUNNING == "RUNNING"
    assert JobStatus.SUCCESS == "SUCCESS"
    assert JobStatus.FAILED == "FAILED"
    assert JobStatus.CANCELLED == "CANCELLED"


# ── Exception Tests ─────────────────────────────────────────────────────


def test_fabric_environment_error():
    """FabricEnvironmentError should include environment in message."""
    err = FabricEnvironmentError("STAGING", "not allowed")
    assert "STAGING" in str(err)
    assert "INV-05" in str(err)
    assert err.environment == "STAGING"


def test_fabric_authentication_error():
    """FabricAuthenticationError should be informative."""
    err = FabricAuthenticationError("invalid credentials")
    assert "invalid credentials" in str(err)


def test_fabric_api_error():
    """FabricAPIError should include status code."""
    err = FabricAPIError(403, "forbidden")
    assert err.status_code == 403
    assert "403" in str(err)
    assert "forbidden" in str(err)


# ── FabricClient.from_settings Tests ────────────────────────────────────


def test_from_settings_missing_tenant_id():
    """from_settings should raise when FABRIC_TENANT_ID is missing."""
    import os
    # Clear any existing settings
    for key in ["AADAP_FABRIC_TENANT_ID", "AADAP_FABRIC_CLIENT_ID",
                "AADAP_FABRIC_CLIENT_SECRET", "AADAP_FABRIC_WORKSPACE_ID"]:
        os.environ.pop(key, None)

    with pytest.raises(ValueError, match="TENANT_ID"):
        FabricClient.from_settings()


def test_from_settings_missing_client_id():
    """from_settings should raise when FABRIC_CLIENT_ID is missing."""
    import os
    os.environ["AADAP_FABRIC_TENANT_ID"] = "test-tenant"
    os.environ.pop("AADAP_FABRIC_CLIENT_ID", None)

    try:
        with pytest.raises(ValueError, match="CLIENT_ID"):
            FabricClient.from_settings()
    finally:
        os.environ.pop("AADAP_FABRIC_TENANT_ID", None)


def test_from_settings_missing_client_secret():
    """from_settings should raise when FABRIC_CLIENT_SECRET is missing."""
    import os
    os.environ["AADAP_FABRIC_TENANT_ID"] = "test-tenant"
    os.environ["AADAP_FABRIC_CLIENT_ID"] = "test-client"
    os.environ.pop("AADAP_FABRIC_CLIENT_SECRET", None)

    try:
        with pytest.raises(ValueError, match="CLIENT_SECRET"):
            FabricClient.from_settings()
    finally:
        os.environ.pop("AADAP_FABRIC_TENANT_ID", None)
        os.environ.pop("AADAP_FABRIC_CLIENT_ID", None)


def test_from_settings_missing_workspace_id():
    """from_settings should raise when FABRIC_WORKSPACE_ID is missing."""
    import os
    os.environ["AADAP_FABRIC_TENANT_ID"] = "test-tenant"
    os.environ["AADAP_FABRIC_CLIENT_ID"] = "test-client"
    os.environ["AADAP_FABRIC_CLIENT_SECRET"] = "test-secret"
    os.environ.pop("AADAP_FABRIC_WORKSPACE_ID", None)

    try:
        with pytest.raises(ValueError, match="WORKSPACE_ID"):
            FabricClient.from_settings()
    finally:
        os.environ.pop("AADAP_FABRIC_TENANT_ID", None)
        os.environ.pop("AADAP_FABRIC_CLIENT_ID", None)
        os.environ.pop("AADAP_FABRIC_CLIENT_SECRET", None)


def test_from_settings_all_configured():
    """from_settings should create client when all settings are provided."""
    import os
    os.environ["AADAP_FABRIC_TENANT_ID"] = "test-tenant"
    os.environ["AADAP_FABRIC_CLIENT_ID"] = "test-client"
    os.environ["AADAP_FABRIC_CLIENT_SECRET"] = "test-secret"
    os.environ["AADAP_FABRIC_WORKSPACE_ID"] = "test-workspace"
    os.environ["AADAP_FABRIC_LAKEHOUSE_ID"] = "test-lakehouse"

    try:
        client = FabricClient.from_settings()
        assert isinstance(client, FabricClient)
        assert client._tenant_id == "test-tenant"
        assert client._workspace_id == "test-workspace"
        assert client._lakehouse_id == "test-lakehouse"
    finally:
        for key in ["AADAP_FABRIC_TENANT_ID", "AADAP_FABRIC_CLIENT_ID",
                    "AADAP_FABRIC_CLIENT_SECRET", "AADAP_FABRIC_WORKSPACE_ID",
                    "AADAP_FABRIC_LAKEHOUSE_ID"]:
            os.environ.pop(key, None)


# ── Abstract Base Tests ─────────────────────────────────────────────────


def test_valid_environments():
    """BaseFabricClient should define SANDBOX and PRODUCTION."""
    assert "SANDBOX" in BaseFabricClient.VALID_ENVIRONMENTS
    assert "PRODUCTION" in BaseFabricClient.VALID_ENVIRONMENTS


def test_fabric_api_base_url():
    """API base URL should point to fabric.microsoft.com."""
    assert "api.fabric.microsoft.com" in BaseFabricClient.FABRIC_API_BASE


# ── State Mapping Tests ────────────────────────────────────────────────


def test_fabric_state_map():
    """FabricClient state map should correctly map all Fabric states."""
    expected = {
        "NotStarted": JobStatus.PENDING,
        "InProgress": JobStatus.RUNNING,
        "Completed": JobStatus.SUCCESS,
        "Failed": JobStatus.FAILED,
        "Cancelled": JobStatus.CANCELLED,
        "Deduped": JobStatus.SUCCESS,
    }
    assert FabricClient._FABRIC_STATE_MAP == expected


# ── Utility Tests ───────────────────────────────────────────────────────


def test_as_text_with_none():
    """_as_text should return None for None input."""
    assert FabricClient._as_text(None) is None


def test_as_text_with_string():
    """_as_text should pass through strings."""
    assert FabricClient._as_text("hello") == "hello"


def test_as_text_with_enum():
    """_as_text should extract .value from enums."""
    assert FabricClient._as_text(JobStatus.SUCCESS) == "SUCCESS"


# ── Multiple Job Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_multiple_concurrent_jobs(mock_client):
    """Multiple jobs should be tracked independently."""
    jobs = []
    for i in range(5):
        result = await mock_client.submit_job(
            task_id=uuid.uuid4(),
            code=f"SELECT {i}",
            environment="SANDBOX",
            language="python",
        )
        jobs.append(result)

    # Each job should have a unique ID
    job_ids = [j.job_id for j in jobs]
    assert len(set(job_ids)) == 5

    # All should succeed
    for job in jobs:
        output = await mock_client.get_job_output(job.job_id)
        assert output.status == JobStatus.SUCCESS
