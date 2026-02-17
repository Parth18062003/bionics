"""
AADAP — In-Memory Store TTL & Namespace Tests
================================================
DoD: "TTL verified."
"""

from __future__ import annotations

import asyncio
import time

import pytest

from aadap.core.memory_store import (
    InMemoryBackend,
    MemoryStoreClient,
    MemoryNamespace,
    _NAMESPACE_TTLS,
)


@pytest.fixture
def client():
    """Provide a MemoryStoreClient backed by InMemoryBackend."""
    return MemoryStoreClient(InMemoryBackend())


@pytest.mark.asyncio
async def test_set_with_default_ttl(client):
    """Keys are set with the configured default TTL."""
    await client.set_with_ttl(
        MemoryNamespace.WORKING_MEMORY, "key1", b"value1"
    )
    result = await client.get(MemoryNamespace.WORKING_MEMORY, "key1")
    assert result == b"value1"

    # Verify key has a TTL (not -1 or -2)
    remaining = await client.ttl(MemoryNamespace.WORKING_MEMORY, "key1")
    assert remaining > 0


@pytest.mark.asyncio
async def test_set_with_custom_ttl(client):
    """Custom TTL overrides namespace default."""
    await client.set_with_ttl(
        MemoryNamespace.SESSIONS, "sess1", b"data", ttl=120
    )
    remaining = await client.ttl(MemoryNamespace.SESSIONS, "sess1")
    # Should be close to 120 (within margin for test execution)
    assert 110 <= remaining <= 120


@pytest.mark.asyncio
async def test_namespace_prefix(client):
    """Keys include the namespace prefix."""
    await client.set_with_ttl(
        MemoryNamespace.CHECKPOINTS, "cp1", b"state"
    )
    # Verify via raw backend that key has correct prefix
    raw_keys = list(client.raw._data.keys())
    assert any("aadap:cp:cp1" in k for k in raw_keys)


@pytest.mark.asyncio
async def test_get_returns_value(client):
    """Get returns value from namespaced key."""
    await client.set_with_ttl(
        MemoryNamespace.WORKING_MEMORY, "k", b"test-value"
    )
    result = await client.get(MemoryNamespace.WORKING_MEMORY, "k")
    assert result == b"test-value"


@pytest.mark.asyncio
async def test_delete_key(client):
    """Delete removes the namespaced key."""
    await client.set_with_ttl(
        MemoryNamespace.TOKEN_TRACKING, "t1", b"data"
    )
    result = await client.delete(MemoryNamespace.TOKEN_TRACKING, "t1")
    assert result == 1
    # Key should be gone
    assert await client.get(MemoryNamespace.TOKEN_TRACKING, "t1") is None


@pytest.mark.asyncio
async def test_ping(client):
    """Ping returns True when store is healthy."""
    assert await client.ping() is True


@pytest.mark.asyncio
async def test_ping_failure():
    """Ping returns False when store raises an exception."""
    backend = InMemoryBackend()

    # Monkey-patch ping to raise
    async def _broken_ping():
        raise ConnectionError("Store down")

    backend.ping = _broken_ping
    c = MemoryStoreClient(backend)
    assert await c.ping() is False


def test_namespace_ttls_defined():
    """All namespaces have TTL configuration."""
    for ns in MemoryNamespace:
        assert ns in _NAMESPACE_TTLS, f"Missing TTL config for {ns}"


def test_checkpoint_ttl_is_24h():
    """Checkpoint TTL is 24 hours as designed."""
    assert _NAMESPACE_TTLS[MemoryNamespace.CHECKPOINTS] == 86400


@pytest.mark.asyncio
async def test_expired_key_returns_none():
    """Expired keys behave like cache miss (Redis behavior)."""
    backend = InMemoryBackend()
    c = MemoryStoreClient(backend)

    await c.set_with_ttl(
        MemoryNamespace.WORKING_MEMORY, "expire-me", b"value", ttl=1
    )

    # Key should exist now
    assert await c.get(MemoryNamespace.WORKING_MEMORY, "expire-me") == b"value"

    # Simulate expiration by manipulating the backend's stored timestamp
    full_key = "aadap:wm:expire-me"
    with backend._lock:
        val, _ = backend._data[full_key]
        backend._data[full_key] = (val, time.monotonic() - 1)

    # Now should return None (cache miss)
    assert await c.get(MemoryNamespace.WORKING_MEMORY, "expire-me") is None
    assert await c.ttl(MemoryNamespace.WORKING_MEMORY, "expire-me") == -2


@pytest.mark.asyncio
async def test_exists(client):
    """exists() returns True for live keys, False for missing."""
    assert await client.exists(MemoryNamespace.WORKING_MEMORY, "nope") is False
    await client.set_with_ttl(
        MemoryNamespace.WORKING_MEMORY, "yes", b"data"
    )
    assert await client.exists(MemoryNamespace.WORKING_MEMORY, "yes") is True
