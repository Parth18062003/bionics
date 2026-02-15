"""
AADAP — Redis TTL & Namespace Tests
=====================================
DoD: "Redis TTL verified."
"""

from __future__ import annotations

import pytest

from aadap.core.redis import RedisClient, RedisNamespace, _NAMESPACE_TTLS


@pytest.mark.asyncio
async def test_set_with_default_ttl(mock_redis_client):
    """Keys are set with the configured default TTL."""
    await mock_redis_client.set_with_ttl(
        RedisNamespace.WORKING_MEMORY, "key1", b"value1"
    )
    mock_redis_client._client.set.assert_called_once()
    call_kwargs = mock_redis_client._client.set.call_args
    # Verify key is namespaced
    assert call_kwargs[0][0] == "aadap:wm:key1"
    # Verify TTL is passed
    assert call_kwargs[1]["ex"] > 0


@pytest.mark.asyncio
async def test_set_with_custom_ttl(mock_redis_client):
    """Custom TTL overrides namespace default."""
    await mock_redis_client.set_with_ttl(
        RedisNamespace.SESSIONS, "sess1", b"data", ttl=120
    )
    call_kwargs = mock_redis_client._client.set.call_args
    assert call_kwargs[1]["ex"] == 120


@pytest.mark.asyncio
async def test_namespace_prefix(mock_redis_client):
    """Keys include the namespace prefix."""
    await mock_redis_client.set_with_ttl(
        RedisNamespace.CHECKPOINTS, "cp1", b"state"
    )
    call_kwargs = mock_redis_client._client.set.call_args
    assert call_kwargs[0][0] == "aadap:cp:cp1"


@pytest.mark.asyncio
async def test_get_returns_value(mock_redis_client):
    """Get returns value from namespaced key."""
    mock_redis_client._client.get.return_value = b"test-value"
    result = await mock_redis_client.get(RedisNamespace.WORKING_MEMORY, "k")
    assert result == b"test-value"
    mock_redis_client._client.get.assert_called_once_with("aadap:wm:k")


@pytest.mark.asyncio
async def test_delete_key(mock_redis_client):
    """Delete removes the namespaced key."""
    await mock_redis_client.delete(RedisNamespace.TOKEN_TRACKING, "t1")
    mock_redis_client._client.delete.assert_called_once_with("aadap:tt:t1")


@pytest.mark.asyncio
async def test_ping(mock_redis_client):
    """Ping returns True when Redis is healthy."""
    assert await mock_redis_client.ping() is True


@pytest.mark.asyncio
async def test_ping_failure(mock_redis_client):
    """Ping returns False when Redis is down."""
    mock_redis_client._client.ping.side_effect = ConnectionError
    assert await mock_redis_client.ping() is False


def test_namespace_ttls_defined():
    """All namespaces have TTL configuration."""
    for ns in RedisNamespace:
        assert ns in _NAMESPACE_TTLS, f"Missing TTL config for {ns}"


def test_checkpoint_ttl_is_24h():
    """Checkpoint TTL is 24 hours as designed."""
    assert _NAMESPACE_TTLS[RedisNamespace.CHECKPOINTS] == 86400
