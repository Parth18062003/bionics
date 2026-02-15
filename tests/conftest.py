"""
AADAP — Test Fixtures
======================
Shared pytest fixtures for Phase 1 tests.

Uses testcontainers for PostgreSQL and Redis when available,
falls back to mocks for fast unit testing.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ── Override settings BEFORE any app import ──────────────────────────────
@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Ensure a fresh Settings instance for each test."""
    from aadap.core.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings():
    """Return a settings instance with test defaults."""
    os.environ.setdefault("AADAP_ENVIRONMENT", "development")
    os.environ.setdefault("AADAP_LOG_LEVEL", "DEBUG")
    os.environ.setdefault("AADAP_LOG_FORMAT", "console")
    from aadap.core.config import get_settings
    return get_settings()


# ── Mock DB engine ───────────────────────────────────────────────────────
@pytest.fixture
def mock_db_engine():
    """Provide a mock async engine for tests that don't need real DB."""
    engine = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=MagicMock())
    engine.connect = MagicMock(return_value=_async_cm(conn))
    return engine


# ── Mock Redis ───────────────────────────────────────────────────────────
@pytest.fixture
def mock_redis_client():
    """Provide a mock RedisClient for tests that don't need real Redis."""
    from aadap.core.redis import RedisClient
    inner = AsyncMock()
    inner.ping = AsyncMock(return_value=True)
    inner.set = AsyncMock()
    inner.get = AsyncMock(return_value=None)
    inner.delete = AsyncMock(return_value=1)
    inner.ttl = AsyncMock(return_value=3600)
    inner.exists = AsyncMock(return_value=False)
    inner.aclose = AsyncMock()
    return RedisClient(inner)


# ── HTTP client (with mocked infra) ─────────────────────────────────────
@pytest.fixture
async def client(mock_db_engine, mock_redis_client):
    """
    AsyncClient wired to the FastAPI app with mocked DB/Redis.

    Patches init_db/init_redis/close_db/close_redis so the lifespan
    doesn't attempt real connections.
    """
    import aadap.db.session as sess_mod
    import aadap.core.redis as redis_mod

    # Patch session module state
    sess_mod._engine = mock_db_engine
    sess_mod._session_factory = MagicMock()

    # Patch redis module state
    redis_mod._redis_client = mock_redis_client

    with (
        patch.object(sess_mod, "init_db", new_callable=AsyncMock, return_value=mock_db_engine),
        patch.object(sess_mod, "close_db", new_callable=AsyncMock),
        patch.object(redis_mod, "init_redis", new_callable=AsyncMock, return_value=mock_redis_client),
        patch.object(redis_mod, "close_redis", new_callable=AsyncMock),
    ):
        from aadap.main import create_app
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    # Cleanup module state
    sess_mod._engine = None
    sess_mod._session_factory = None
    redis_mod._redis_client = None


# ── Helpers ──────────────────────────────────────────────────────────────
class _async_cm:
    """Turn an async mock into an async context manager."""
    def __init__(self, value):
        self._value = value
    async def __aenter__(self):
        return self._value
    async def __aexit__(self, *args):
        pass
