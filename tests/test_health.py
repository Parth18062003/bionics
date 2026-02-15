"""
AADAP — Health Endpoint Tests
===============================
DoD: "Health endpoint responds."
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_returns_200(client):
    """Health endpoint returns 200 with structured response."""
    resp = await client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_health_response_structure(client):
    """Response contains status, postgres, and redis fields."""
    resp = await client.get("/health")
    data = resp.json()

    assert "status" in data
    assert "postgres" in data
    assert "redis" in data


@pytest.mark.asyncio
async def test_health_all_ok(client):
    """When DB and Redis are reachable, overall status is 'healthy'."""
    resp = await client.get("/health")
    data = resp.json()

    assert data["status"] == "healthy"
    assert data["postgres"] == "ok"
    assert data["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_degraded_on_redis_failure(client, mock_redis_client):
    """When Redis is unreachable, status degrades."""
    mock_redis_client._client.ping.side_effect = ConnectionError("Redis down")

    resp = await client.get("/health")
    data = resp.json()

    assert data["status"] == "degraded"
    assert data["redis"] == "error"
