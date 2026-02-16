"""
AADAP — Working Memory Tests
================================
Tests for Redis-backed TTL-bound working memory.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from aadap.core.redis import RedisClient, RedisNamespace
from aadap.memory.working_memory import WorkingMemory


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """Create a mock RedisClient for working memory tests."""
    inner = AsyncMock()
    inner.set = AsyncMock()
    inner.get = AsyncMock(return_value=None)
    inner.delete = AsyncMock(return_value=1)
    inner.scan = AsyncMock(return_value=(0, []))
    return RedisClient(inner)


@pytest.fixture
def wm(mock_redis):
    """Create a WorkingMemory instance with mock Redis."""
    return WorkingMemory(mock_redis)


# ── Store / Recall Round-Trip ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_and_recall(wm, mock_redis):
    """store() persists data that can be retrieved via recall()."""
    data = {"task": "build pipeline", "step": 3}
    await wm.store("agent-1", "context", data)

    # Verify set was called with TTL
    mock_redis._client.set.assert_called_once()
    call_args = mock_redis._client.set.call_args
    # Key should contain agent ID
    assert "agent-1:context" in call_args[0][0]
    # Value should be JSON-encoded
    stored_value = call_args[0][1]
    assert json.loads(stored_value) == data
    # TTL should be set
    assert call_args[1]["ex"] > 0


@pytest.mark.asyncio
async def test_recall_returns_decoded_json(wm, mock_redis):
    """recall() JSON-decodes the stored value."""
    data = {"key": "value", "count": 42}
    mock_redis._client.get.return_value = json.dumps(data).encode("utf-8")
    result = await wm.recall("agent-1", "context")
    assert result == data


@pytest.mark.asyncio
async def test_recall_returns_none_for_missing(wm):
    """recall() returns None for expired or missing keys."""
    result = await wm.recall("agent-1", "nonexistent")
    assert result is None


# ── TTL Enforcement ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ttl_always_set(wm, mock_redis):
    """Every store() call passes a TTL — no entry without TTL."""
    await wm.store("agent-1", "key1", {"data": True})
    call_kwargs = mock_redis._client.set.call_args
    assert "ex" in call_kwargs[1]
    assert call_kwargs[1]["ex"] > 0


@pytest.mark.asyncio
async def test_custom_ttl_honoured(wm, mock_redis):
    """Custom TTL is passed through to Redis."""
    await wm.store("agent-1", "key1", {"data": True}, ttl=300)
    call_kwargs = mock_redis._client.set.call_args
    assert call_kwargs[1]["ex"] == 300


# ── Forget ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forget_deletes_key(wm, mock_redis):
    """forget() calls delete on the correct namespaced key."""
    await wm.forget("agent-1", "context")
    mock_redis._client.delete.assert_called_once()
    deleted_key = mock_redis._client.delete.call_args[0][0]
    assert "agent-1:context" in deleted_key


# ── List Keys ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_keys(wm, mock_redis):
    """list_keys() returns stripped key names for an agent."""
    prefix = "aadap:wm:agent-1:"
    mock_redis._client.scan.return_value = (
        0,
        [f"{prefix}key1".encode(), f"{prefix}key2".encode()],
    )
    keys = await wm.list_keys("agent-1")
    assert sorted(keys) == ["key1", "key2"]


@pytest.mark.asyncio
async def test_list_keys_empty(wm, mock_redis):
    """list_keys() returns empty list when no keys exist."""
    mock_redis._client.scan.return_value = (0, [])
    keys = await wm.list_keys("agent-1")
    assert keys == []


# ── Input Validation ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_empty_agent_id_raises(wm):
    """store() raises ValueError on empty agent_id."""
    with pytest.raises(ValueError, match="agent_id"):
        await wm.store("", "key", {"data": True})


@pytest.mark.asyncio
async def test_store_empty_key_raises(wm):
    """store() raises ValueError on empty key."""
    with pytest.raises(ValueError, match="key"):
        await wm.store("agent-1", "", {"data": True})
