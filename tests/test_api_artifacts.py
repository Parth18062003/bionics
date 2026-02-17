"""
AADAP — Artifact API Tests
=============================
Tests for Phase 7 artifact viewer endpoints.

Validates:
- Listing artifacts for a task
- Getting artifact detail
- 404 for missing artifacts
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from aadap.api.deps import get_session
from aadap.db.models import Artifact


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_artifact():
    """Create a mock Artifact ORM object."""
    return Artifact(
        id=uuid.uuid4(),
        task_id=uuid.uuid4(),
        artifact_type="code",
        name="generated_query.sql",
        content="SELECT * FROM users WHERE active = 1;",
        content_hash="sha256:abc123",
        storage_uri=None,
        metadata_={"language": "sql"},
        created_at=datetime.now(timezone.utc),
    )


def _override_session(mock_result):
    """Create a session dependency override returning mock query results."""
    async def override():
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        yield mock_session
    return override


# ── List Artifacts ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_artifacts(test_app, client, mock_artifact):
    """GET /api/v1/tasks/{task_id}/artifacts should return artifacts."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_artifact]

    test_app.dependency_overrides[get_session] = _override_session(mock_result)
    try:
        response = await client.get(
            f"/api/v1/tasks/{mock_artifact.task_id}/artifacts"
        )
    finally:
        test_app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "generated_query.sql"
    assert data[0]["artifact_type"] == "code"


@pytest.mark.asyncio
async def test_list_artifacts_empty(test_app, client):
    """GET /api/v1/tasks/{task_id}/artifacts with no artifacts returns empty."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    test_app.dependency_overrides[get_session] = _override_session(mock_result)
    try:
        response = await client.get(
            f"/api/v1/tasks/{uuid.uuid4()}/artifacts"
        )
    finally:
        test_app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json() == []


# ── Get Artifact Detail ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_artifact_detail(test_app, client, mock_artifact):
    """GET /api/v1/tasks/{task_id}/artifacts/{id} should return detail with content."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_artifact

    test_app.dependency_overrides[get_session] = _override_session(mock_result)
    try:
        response = await client.get(
            f"/api/v1/tasks/{mock_artifact.task_id}/artifacts/{mock_artifact.id}"
        )
    finally:
        test_app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "generated_query.sql"
    assert "SELECT" in data["content"]
    assert data["content_hash"] == "sha256:abc123"


@pytest.mark.asyncio
async def test_get_artifact_not_found(test_app, client):
    """GET /api/v1/tasks/{task_id}/artifacts/{bad_id} should return 404."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    test_app.dependency_overrides[get_session] = _override_session(mock_result)
    try:
        response = await client.get(
            f"/api/v1/tasks/{uuid.uuid4()}/artifacts/{uuid.uuid4()}"
        )
    finally:
        test_app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 404
