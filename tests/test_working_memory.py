"""
AADAP — Working Memory Tests
================================
Tests for TTL-bound working memory backed by in-memory store.
"""

from __future__ import annotations

import json
import time

import pytest

from aadap.core.memory_store import InMemoryBackend, MemoryStoreClient, MemoryNamespace
from aadap.memory.working_memory import WorkingMemory


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_store():
    """Create a MemoryStoreClient backed by InMemoryBackend for working memory tests."""
    return MemoryStoreClient(InMemoryBackend())


@pytest.fixture
def wm(mock_store):
    """Create a WorkingMemory instance with in-memory backend."""
    return WorkingMemory(mock_store)


# ── Store / Recall Round-Trip ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_store_and_recall(wm):
    """store() persists data that can be retrieved via recall()."""
    data = {"task": "build pipeline", "step": 3}
    await wm.store("agent-1", "context", data)

    result = await wm.recall("agent-1", "context")
    assert result == data


@pytest.mark.asyncio
async def test_recall_returns_decoded_json(wm):
    """recall() JSON-decodes the stored value."""
    data = {"key": "value", "count": 42}
    await wm.store("agent-1", "context", data)
    result = await wm.recall("agent-1", "context")
    assert result == data


@pytest.mark.asyncio
async def test_recall_returns_none_for_missing(wm):
    """recall() returns None for expired or missing keys."""
    result = await wm.recall("agent-1", "nonexistent")
    assert result is None


# ── TTL Enforcement ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ttl_always_set(wm, mock_store):
    """Every store() call applies a TTL — no entry without TTL."""
    await wm.store("agent-1", "key1", {"data": True})
    # Verify key has a positive TTL
    remaining = await mock_store.ttl(
        MemoryNamespace.WORKING_MEMORY, "agent-1:key1"
    )
    assert remaining > 0


@pytest.mark.asyncio
async def test_custom_ttl_honoured(wm, mock_store):
    """Custom TTL is passed through to the store."""
    await wm.store("agent-1", "key1", {"data": True}, ttl=300)
    remaining = await mock_store.ttl(
        MemoryNamespace.WORKING_MEMORY, "agent-1:key1"
    )
    # Should be close to 300
    assert 290 <= remaining <= 300


# ── Forget ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forget_deletes_key(wm):
    """forget() removes key from the store."""
    await wm.store("agent-1", "context", {"data": True})
    assert await wm.recall("agent-1", "context") is not None

    await wm.forget("agent-1", "context")
    assert await wm.recall("agent-1", "context") is None


# ── List Keys ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_keys(wm):
    """list_keys() returns stripped key names for an agent."""
    await wm.store("agent-1", "key1", {"a": 1})
    await wm.store("agent-1", "key2", {"b": 2})
    keys = await wm.list_keys("agent-1")
    assert sorted(keys) == ["key1", "key2"]


@pytest.mark.asyncio
async def test_list_keys_empty(wm):
    """list_keys() returns empty list when no keys exist."""
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


# ── TTL Expiration ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_expired_key_returns_none_on_recall(wm, mock_store):
    """Expired working memory entries return None (cache miss)."""
    await wm.store("agent-1", "temp", {"data": True}, ttl=1)

    # Verify it exists
    assert await wm.recall("agent-1", "temp") is not None

    # Simulate expiration
    full_key = "aadap:wm:agent-1:temp"
    backend = mock_store.raw
    with backend._lock:
        val, _ = backend._data[full_key]
        backend._data[full_key] = (val, time.monotonic() - 1)

    # Should be a cache miss now
    assert await wm.recall("agent-1", "temp") is None
