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
    assert "redis" in data  # Field name preserved (public API)


@pytest.mark.asyncio
async def test_health_all_ok(client):
    """When DB and store are reachable, overall status is 'healthy'."""
    resp = await client.get("/health")
    data = resp.json()

    assert data["status"] == "healthy"
    assert data["postgres"] == "ok"
    assert data["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_degraded_on_store_failure(client, mock_memory_store_client):
    """When store is unreachable, status degrades."""
    # Monkey-patch ping to raise
    async def _broken_ping():
        raise ConnectionError("Store down")

    mock_memory_store_client._client.ping = _broken_ping

    resp = await client.get("/health")
    data = resp.json()

    assert data["status"] == "degraded"
    assert data["redis"] == "error"
