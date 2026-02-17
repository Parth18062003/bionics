"""
AADAP — In-Memory Key-Value Store
====================================
Thread-safe in-memory backend with namespace isolation and per-namespace TTL.

Drop-in replacement for the previous Redis-backed implementation.
All public APIs (MemoryStoreClient, MemoryNamespace, init_memory_store, get_memory_store,
close_memory_store) are preserved in functionality.

Supports:
- Tier 1 Working Memory (DATA_AND_STATE.md)
- Namespace isolation for checkpoints, token tracking, working memory
- Configurable default TTL
- Lazy key expiration (expired keys return cache miss)

Limitation:
    This is a process-local store.  There is no cross-process sharing.
    All current AADAP usage is single-process, so this is safe.

Usage:
    from aadap.core.memory_store import get_memory_store, MemoryNamespace
    store = await get_memory_store()
    await store.set_with_ttl(MemoryNamespace.WORKING_MEMORY, "key", "value")
"""

from __future__ import annotations

import fnmatch
import threading
import time
from enum import StrEnum
from typing import Any

from aadap.core.config import get_settings

# ── Namespaces ──────────────────────────────────────────────────────────
# Pre-declared for all known consumers across phases.
# Phase 1: configuration only.  Phase 2+: consumed.


class MemoryNamespace(StrEnum):
    """Logical namespaces for key isolation."""
    WORKING_MEMORY = "wm"       # Phase 6: agent working memory
    CHECKPOINTS = "cp"          # Phase 2: orchestrator checkpoints
    TOKEN_TRACKING = "tt"       # Phase 3: per-task token accounting
    SESSIONS = "sess"           # Phase 7: user sessions


# Per-namespace TTL overrides (seconds).  Falls back to config default.
_NAMESPACE_TTLS: dict[MemoryNamespace, int | None] = {
    MemoryNamespace.WORKING_MEMORY: None,    # uses config default
    MemoryNamespace.CHECKPOINTS: 86400,      # 24 hours
    MemoryNamespace.TOKEN_TRACKING: 7200,    # 2 hours
    MemoryNamespace.SESSIONS: 3600,          # 1 hour
}


# ── In-Memory Backend ──────────────────────────────────────────────────


class InMemoryBackend:
    """
    Thread-safe in-memory key-value store with TTL support.

    Drop-in replacement for ``redis.asyncio.Redis``.  All methods are
    async to preserve the same await semantics used by ``MemoryStoreClient``.

    TTL is implemented via monotonic timestamps with lazy eviction:
    expired keys are removed on access rather than via a background thread.
    """

    def __init__(self) -> None:
        # Mapping: key → (raw_bytes, expiry_monotonic_or_None)
        self._data: dict[str, tuple[bytes, float | None]] = {}
        self._lock = threading.Lock()

    def _is_alive(self, key: str) -> bool:
        """Check if key exists and is not expired.  Evicts if expired."""
        if key not in self._data:
            return False
        _, expiry = self._data[key]
        if expiry is not None and time.monotonic() > expiry:
            del self._data[key]
            return False
        return True

    # ── Redis-compatible async API ──────────────────────────────────────

    async def set(
        self,
        key: str,
        value: str | bytes,
        *,
        ex: int | None = None,
    ) -> None:
        with self._lock:
            expiry = time.monotonic() + ex if ex is not None else None
            raw = value.encode("utf-8") if isinstance(value, str) else value
            self._data[key] = (raw, expiry)

    async def get(self, key: str) -> bytes | None:
        with self._lock:
            if not self._is_alive(key):
                return None
            return self._data[key][0]

    async def delete(self, *keys: str) -> int:
        with self._lock:
            count = 0
            for k in keys:
                if k in self._data:
                    del self._data[k]
                    count += 1
            return count

    async def ttl(self, key: str) -> int:
        """Return remaining TTL.  -1 = no expiry, -2 = missing/expired."""
        with self._lock:
            if not self._is_alive(key):
                return -2
            _, expiry = self._data[key]
            if expiry is None:
                return -1
            return max(0, int(expiry - time.monotonic()))

    async def exists(self, *keys: str) -> int:
        with self._lock:
            return sum(1 for k in keys if self._is_alive(k))

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        """No-op — nothing to close for in-memory store."""
        pass

    async def scan(
        self,
        cursor: int = 0,
        *,
        match: str | None = None,
        count: int = 100,
    ) -> tuple[int, list[str]]:
        """
        Scan keys matching a glob pattern.

        Always returns cursor=0 (single-pass), matching Redis SCAN
        semantics when iteration is complete.
        """
        with self._lock:
            alive_keys = [k for k in list(self._data) if self._is_alive(k)]
            if match:
                alive_keys = [
                    k for k in alive_keys if fnmatch.fnmatch(k, match)
                ]
            return (0, alive_keys)


class MemoryStoreClient:
    """
    Thin async wrapper with namespace-aware key prefixing and TTL
    enforcement.

    Backed by ``InMemoryBackend`` (process-local, thread-safe).
    """

    def __init__(self, client: InMemoryBackend) -> None:
        self._client = client

    # ── Key helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _prefixed(ns: MemoryNamespace, key: str) -> str:
        return f"aadap:{ns.value}:{key}"

    def _ttl_for(self, ns: MemoryNamespace) -> int:
        override = _NAMESPACE_TTLS.get(ns)
        if override is not None:
            return override
        return get_settings().memory_default_ttl_seconds

    # ── Public API ───────────────────────────────────────────────────────

    async def set_with_ttl(
        self,
        ns: MemoryNamespace,
        key: str,
        value: str | bytes,
        ttl: int | None = None,
    ) -> None:
        """Set a key with namespace prefix and TTL."""
        full_key = self._prefixed(ns, key)
        effective_ttl = ttl if ttl is not None else self._ttl_for(ns)
        await self._client.set(full_key, value, ex=effective_ttl)

    async def get(self, ns: MemoryNamespace, key: str) -> bytes | None:
        """Get a value by namespace + key."""
        return await self._client.get(self._prefixed(ns, key))

    async def delete(self, ns: MemoryNamespace, key: str) -> int:
        """Delete a key. Returns number of keys deleted (0 or 1)."""
        return await self._client.delete(self._prefixed(ns, key))

    async def ttl(self, ns: MemoryNamespace, key: str) -> int:
        """Return remaining TTL in seconds.  -1 = no expiry, -2 = missing."""
        return await self._client.ttl(self._prefixed(ns, key))

    async def exists(self, ns: MemoryNamespace, key: str) -> bool:
        """Check if a key exists."""
        return bool(await self._client.exists(self._prefixed(ns, key)))

    async def ping(self) -> bool:
        """Health check.  Returns True if store is responsive."""
        try:
            return await self._client.ping()
        except Exception:
            return False

    async def close(self) -> None:
        """Gracefully close (no-op for in-memory store)."""
        await self._client.aclose()

    @property
    def raw(self) -> InMemoryBackend:
        """Escape hatch for advanced operations.  Use sparingly."""
        return self._client


# ── Module-level singleton ──────────────────────────────────────────────

_memory_store_client: MemoryStoreClient | None = None


async def init_memory_store() -> MemoryStoreClient:
    """
    Initialize the module-level in-memory client.

    Called once during application startup.
    """
    global _memory_store_client
    backend = InMemoryBackend()
    _memory_store_client = MemoryStoreClient(backend)
    return _memory_store_client


async def get_memory_store() -> MemoryStoreClient:
    """Return the initialized client.  Raises if not initialized."""
    if _memory_store_client is None:
        raise RuntimeError(
            "Memory store client not initialized. Call init_memory_store() during startup."
        )
    return _memory_store_client


async def close_memory_store() -> None:
    """Shutdown the in-memory store."""
    global _memory_store_client
    if _memory_store_client is not None:
        await _memory_store_client.close()
        _memory_store_client = None
