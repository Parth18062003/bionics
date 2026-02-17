"""
AADAP — Task API Tests
========================
Tests for Phase 7 task CRUD and transition endpoints.

Validates:
- Task creation delegates to orchestrator
- Task listing with pagination and state filter
- State transition via orchestrator graph
- Correlation ID propagation in responses
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aadap.api.deps import get_session
from aadap.db.models import Task


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_task():
    """Create a mock Task ORM object."""
    return Task(
        id=uuid.uuid4(),
        title="Test Task",
        description="A test task",
        current_state="SUBMITTED",
        priority=1,
        environment="SANDBOX",
        created_by="system",
        token_budget=50_000,
        tokens_used=0,
        retry_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _override_session(mock_result):
    """Create a session dependency override returning mock query results."""
    async def override():
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        yield mock_session
    return override


# ── Task Creation Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_task_returns_201(test_app, client, mock_task):
    """POST /api/v1/tasks should create a task and return 201."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_task

    test_app.dependency_overrides[get_session] = _override_session(mock_result)

    with patch(
        "aadap.api.routes.tasks.create_task",
        new_callable=AsyncMock,
        return_value=mock_task.id,
    ):
        try:
            response = await client.post(
                "/api/v1/tasks",
                json={
                    "title": "Test Task",
                    "description": "A test task",
                    "priority": 1,
                    "environment": "SANDBOX",
                },
            )
        finally:
            test_app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Task"
    assert data["current_state"] == "SUBMITTED"
    assert data["environment"] == "SANDBOX"


@pytest.mark.asyncio
async def test_create_task_requires_title(client):
    """POST /api/v1/tasks without title should return 422."""
    response = await client.post(
        "/api/v1/tasks",
        json={"description": "No title"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_task_validates_environment(client):
    """POST /api/v1/tasks with invalid environment should return 422."""
    response = await client.post(
        "/api/v1/tasks",
        json={
            "title": "Bad Env Task",
            "environment": "STAGING",  # Not SANDBOX or PRODUCTION
        },
    )
    assert response.status_code == 422


# ── Task Listing Tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tasks_invalid_state(test_app, client):
    """GET /api/v1/tasks?state=INVALID should return 400."""
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0
    mock_result.scalars.return_value.all.return_value = []

    test_app.dependency_overrides[get_session] = _override_session(mock_result)
    try:
        response = await client.get("/api/v1/tasks?state=INVALID")
    finally:
        test_app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 400


# ── Correlation ID Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_correlation_id_in_response(client):
    """Every response must include X-Correlation-ID header."""
    response = await client.get("/health")
    assert "x-correlation-id" in response.headers


@pytest.mark.asyncio
async def test_correlation_id_propagated(client):
    """Custom X-Correlation-ID is echoed back."""
    custom_cid = str(uuid.uuid4())
    response = await client.get(
        "/health",
        headers={"X-Correlation-ID": custom_cid},
    )
    assert response.headers.get("x-correlation-id") == custom_cid
