"""
AADAP — Test Fixtures
======================
Shared pytest fixtures for Phase 1 tests.

Uses in-memory backend for fast unit testing.
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


# ── In-Memory Store Client ──────────────────────────────────────────────
@pytest.fixture
def mock_memory_store_client():
    """Provide a MemoryStoreClient backed by InMemoryBackend for tests."""
    from aadap.core.memory_store import InMemoryBackend, MemoryStoreClient
    backend = InMemoryBackend()
    return MemoryStoreClient(backend)


# ── HTTP client (with mocked infra) ─────────────────────────────────────
@pytest.fixture
async def test_app(mock_db_engine, mock_memory_store_client):
    """
    FastAPI app instance with mocked DB and in-memory store.

    Exposes the app so tests can do ``app.dependency_overrides``.
    """
    import aadap.db.session as sess_mod
    import aadap.core.memory_store as mem_mod

    # Patch session module state
    sess_mod._engine = mock_db_engine
    sess_mod._session_factory = MagicMock()

    # Patch memory module state
    mem_mod._memory_store_client = mock_memory_store_client

    with (
        patch.object(sess_mod, "init_db", new_callable=AsyncMock, return_value=mock_db_engine),
        patch.object(sess_mod, "close_db", new_callable=AsyncMock),
        patch.object(mem_mod, "init_memory_store", new_callable=AsyncMock, return_value=mock_memory_store_client),
        patch.object(mem_mod, "close_memory_store", new_callable=AsyncMock),
    ):
        from aadap.main import create_app
        app = create_app()
        yield app

    # Cleanup module state
    sess_mod._engine = None
    sess_mod._session_factory = None
    mem_mod._memory_store_client = None


@pytest.fixture
async def client(test_app):
    """
    AsyncClient wired to the FastAPI app with mocked DB and in-memory store.
    """
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helpers ──────────────────────────────────────────────────────────────
class _async_cm:
    """Turn an async mock into an async context manager."""
    def __init__(self, value):
        self._value = value
    async def __aenter__(self):
        return self._value
    async def __aexit__(self, *args):
        pass
