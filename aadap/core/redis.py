"""
AADAP — Redis Client
=====================
Async Redis client with namespace isolation and per-namespace TTL.

Supports:
- Tier 1 Working Memory (DATA_AND_STATE.md)
- Namespace isolation for checkpoints, token tracking, working memory
- Configurable default TTL

Usage:
    from aadap.core.redis import get_redis, RedisNamespace
    redis = await get_redis()
    await redis.set_with_ttl(RedisNamespace.WORKING_MEMORY, "key", "value")
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import redis.asyncio as aioredis

from aadap.core.config import get_settings

# ── Namespaces ──────────────────────────────────────────────────────────
# Pre-declared for all known consumers across phases.
# Phase 1: configuration only.  Phase 2+: consumed.


class RedisNamespace(StrEnum):
    """Logical namespaces for Redis key isolation."""
    WORKING_MEMORY = "wm"       # Phase 6: agent working memory
    CHECKPOINTS = "cp"          # Phase 2: orchestrator checkpoints
    TOKEN_TRACKING = "tt"       # Phase 3: per-task token accounting
    SESSIONS = "sess"           # Phase 7: user sessions


# Per-namespace TTL overrides (seconds).  Falls back to config default.
_NAMESPACE_TTLS: dict[RedisNamespace, int | None] = {
    RedisNamespace.WORKING_MEMORY: None,    # uses config default
    RedisNamespace.CHECKPOINTS: 86400,      # 24 hours
    RedisNamespace.TOKEN_TRACKING: 7200,    # 2 hours
    RedisNamespace.SESSIONS: 3600,          # 1 hour
}


class RedisClient:
    """
    Thin async wrapper around ``redis.asyncio`` with namespace-aware key
    prefixing and TTL enforcement.
    """

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    # ── Key helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _prefixed(ns: RedisNamespace, key: str) -> str:
        return f"aadap:{ns.value}:{key}"

    def _ttl_for(self, ns: RedisNamespace) -> int:
        override = _NAMESPACE_TTLS.get(ns)
        if override is not None:
            return override
        return get_settings().redis_default_ttl_seconds

    # ── Public API ───────────────────────────────────────────────────────

    async def set_with_ttl(
        self,
        ns: RedisNamespace,
        key: str,
        value: str | bytes,
        ttl: int | None = None,
    ) -> None:
        """Set a key with namespace prefix and TTL."""
        full_key = self._prefixed(ns, key)
        effective_ttl = ttl if ttl is not None else self._ttl_for(ns)
        await self._client.set(full_key, value, ex=effective_ttl)

    async def get(self, ns: RedisNamespace, key: str) -> bytes | None:
        """Get a value by namespace + key."""
        return await self._client.get(self._prefixed(ns, key))

    async def delete(self, ns: RedisNamespace, key: str) -> int:
        """Delete a key. Returns number of keys deleted (0 or 1)."""
        return await self._client.delete(self._prefixed(ns, key))

    async def ttl(self, ns: RedisNamespace, key: str) -> int:
        """Return remaining TTL in seconds.  -1 = no expiry, -2 = missing."""
        return await self._client.ttl(self._prefixed(ns, key))

    async def exists(self, ns: RedisNamespace, key: str) -> bool:
        """Check if a key exists."""
        return bool(await self._client.exists(self._prefixed(ns, key)))

    async def ping(self) -> bool:
        """Health check.  Returns True if Redis is responsive."""
        try:
            return await self._client.ping()
        except Exception:
            return False

    async def close(self) -> None:
        """Gracefully close the connection pool."""
        await self._client.aclose()

    @property
    def raw(self) -> aioredis.Redis:
        """Escape hatch for advanced operations.  Use sparingly."""
        return self._client


# ── Module-level singleton ──────────────────────────────────────────────

_redis_client: RedisClient | None = None


async def init_redis() -> RedisClient:
    """
    Initialize the module-level Redis client.

    Called once during application startup.
    """
    global _redis_client
    settings = get_settings()
    pool = aioredis.ConnectionPool.from_url(
        settings.redis_url,
        max_connections=settings.redis_max_connections,
        decode_responses=False,
    )
    client = aioredis.Redis(connection_pool=pool)
    _redis_client = RedisClient(client)
    return _redis_client


async def get_redis() -> RedisClient:
    """Return the initialized Redis client.  Raises if not initialized."""
    if _redis_client is None:
        raise RuntimeError(
            "Redis client not initialized. Call init_redis() during startup."
        )
    return _redis_client


async def close_redis() -> None:
    """Shutdown the Redis connection pool."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
