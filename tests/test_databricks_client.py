"""
AADAP — Databricks Client Tests
==================================
Tests for Phase 7 Databricks execution client.

Validates:
- MockDatabricksClient job submission and retrieval
- INV-05 environment validation (sandbox isolation)
- Correlation ID forwarding
- Job lifecycle (PENDING → SUCCESS/FAILED)
"""

from __future__ import annotations

import uuid

import pytest

from aadap.integrations.databricks_client import (
    BaseDatabricksClient,
    DatabricksEnvironmentError,
    JobResult,
    JobStatus,
    JobSubmission,
    MockDatabricksClient,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    """Fresh MockDatabricksClient for each test."""
    return MockDatabricksClient()


@pytest.fixture
def failing_client():
    """MockDatabricksClient that simulates failures."""
    return MockDatabricksClient(default_status=JobStatus.FAILED)


# ── Job Submission Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_job_sandbox(mock_client):
    """Submit a job in SANDBOX environment."""
    task_id = uuid.uuid4()
    result = await mock_client.submit_job(
        task_id=task_id,
        code="SELECT 1;",
        environment="SANDBOX",
    )

    assert isinstance(result, JobSubmission)
    assert result.task_id == task_id
    assert result.environment == "SANDBOX"
    assert result.status == JobStatus.PENDING
    assert result.job_id.startswith("mock-job-")


@pytest.mark.asyncio
async def test_submit_job_production(mock_client):
    """Submit a job in PRODUCTION environment."""
    task_id = uuid.uuid4()
    result = await mock_client.submit_job(
        task_id=task_id,
        code="OPTIMIZE table;",
        environment="PRODUCTION",
    )

    assert result.environment == "PRODUCTION"


@pytest.mark.asyncio
async def test_submit_job_with_correlation_id(mock_client):
    """Correlation ID should be forwarded to the job."""
    cid = "test-correlation-123"
    result = await mock_client.submit_job(
        task_id=uuid.uuid4(),
        code="SELECT 1;",
        environment="SANDBOX",
        correlation_id=cid,
    )

    assert result.job_id is not None
    # Verify the job was tracked with correlation ID
    job_data = mock_client._jobs[result.job_id]
    assert job_data["correlation_id"] == cid
    assert job_data["trace_headers"]["X-Correlation-ID"] == cid


# ── INV-05: Environment Validation ─────────────────────────────────────


@pytest.mark.asyncio
async def test_inv05_invalid_environment(mock_client):
    """INV-05: Invalid environment should raise DatabricksEnvironmentError."""
    with pytest.raises(DatabricksEnvironmentError) as exc_info:
        await mock_client.submit_job(
            task_id=uuid.uuid4(),
            code="SELECT 1;",
            environment="STAGING",
        )

    assert "INV-05" in str(exc_info.value)
    assert "STAGING" in str(exc_info.value)


@pytest.mark.asyncio
async def test_inv05_empty_environment(mock_client):
    """INV-05: Empty environment should raise."""
    with pytest.raises(DatabricksEnvironmentError):
        await mock_client.submit_job(
            task_id=uuid.uuid4(),
            code="SELECT 1;",
            environment="",
        )


# ── Job Status Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_job_status_transitions(mock_client):
    """Job status transitions from PENDING to SUCCESS."""
    result = await mock_client.submit_job(
        task_id=uuid.uuid4(),
        code="SELECT 1;",
        environment="SANDBOX",
    )

    # First poll: transitions from PENDING
    status = await mock_client.get_job_status(result.job_id)
    assert status == JobStatus.SUCCESS


@pytest.mark.asyncio
async def test_get_job_status_failure(failing_client):
    """Failing client simulates FAILED status."""
    result = await failing_client.submit_job(
        task_id=uuid.uuid4(),
        code="BAD QUERY;",
        environment="SANDBOX",
    )

    status = await failing_client.get_job_status(result.job_id)
    assert status == JobStatus.FAILED


@pytest.mark.asyncio
async def test_get_job_status_not_found(mock_client):
    """Querying unknown job ID should raise KeyError."""
    with pytest.raises(KeyError):
        await mock_client.get_job_status("nonexistent-job")


# ── Job Output Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_job_output_success(mock_client):
    """Successful job should return output."""
    result = await mock_client.submit_job(
        task_id=uuid.uuid4(),
        code="SELECT 1;",
        environment="SANDBOX",
    )

    output = await mock_client.get_job_output(result.job_id)
    assert isinstance(output, JobResult)
    assert output.status == JobStatus.SUCCESS
    assert output.output == "Mock execution output"
    assert output.error is None
    assert output.duration_ms == 1500


@pytest.mark.asyncio
async def test_get_job_output_failure(failing_client):
    """Failed job should return error."""
    result = await failing_client.submit_job(
        task_id=uuid.uuid4(),
        code="FAIL;",
        environment="SANDBOX",
    )

    output = await failing_client.get_job_output(result.job_id)
    assert output.status == JobStatus.FAILED
    assert output.error is not None
    assert output.output is None


@pytest.mark.asyncio
async def test_get_job_output_not_found(mock_client):
    """Querying output for unknown job should raise KeyError."""
    with pytest.raises(KeyError):
        await mock_client.get_job_output("nonexistent-job")


# ── Abstract Interface Tests ───────────────────────────────────────────


def test_base_client_is_abstract():
    """BaseDatabricksClient cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseDatabricksClient()
