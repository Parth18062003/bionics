"""
AADAP — Working Memory
========================
Redis-backed Tier 1 working memory for agent session context.

All entries are TTL-bound — no entry may exist without a TTL.
Uses ``RedisNamespace.WORKING_MEMORY`` from Phase 1 infrastructure.

Usage:
    from aadap.memory.working_memory import WorkingMemory
    from aadap.core.redis import get_redis

    wm = WorkingMemory(await get_redis())
    await wm.store("agent-1", "context", {"key": "value"})
    data = await wm.recall("agent-1", "context")
"""

from __future__ import annotations

import json

from aadap.core.redis import RedisClient, RedisNamespace


class WorkingMemory:
    """
    Agent-scoped key-value working memory backed by Redis.

    Invariant: every entry is TTL-bound.  The TTL comes from either
    the caller or the namespace default configured in ``_NAMESPACE_TTLS``.
    No entry may persist indefinitely.
    """

    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis
        self._ns = RedisNamespace.WORKING_MEMORY

    # ── Key scheme ──────────────────────────────────────────────────────

    @staticmethod
    def _key(agent_id: str, key: str) -> str:
        """Agent-scoped key within the working memory namespace."""
        return f"{agent_id}:{key}"

    # ── Store ───────────────────────────────────────────────────────────

    async def store(
        self,
        agent_id: str,
        key: str,
        value: dict,
        ttl: int | None = None,
    ) -> None:
        """
        Store a value in working memory.

        Args:
            agent_id: Owning agent identifier.
            key: Logical key within the agent's namespace.
            value: Dict payload (JSON-serialisable).
            ttl: TTL in seconds.  Defaults to namespace TTL (config).

        The value is JSON-encoded before storage.
        TTL is always enforced — even if ``ttl`` is ``None``, the namespace
        default TTL applies.
        """
        if not agent_id or not agent_id.strip():
            raise ValueError("agent_id must not be empty.")
        if not key or not key.strip():
            raise ValueError("key must not be empty.")

        serialised = json.dumps(value, default=str)
        full_key = self._key(agent_id, key)
        await self._redis.set_with_ttl(self._ns, full_key, serialised, ttl=ttl)

    # ── Recall ──────────────────────────────────────────────────────────

    async def recall(self, agent_id: str, key: str) -> dict | None:
        """
        Retrieve a value from working memory.

        Returns ``None`` if the key has expired or does not exist.
        """
        full_key = self._key(agent_id, key)
        raw = await self._redis.get(self._ns, full_key)
        if raw is None:
            return None
        return json.loads(raw)

    # ── Forget ──────────────────────────────────────────────────────────

    async def forget(self, agent_id: str, key: str) -> None:
        """Delete a key from working memory."""
        full_key = self._key(agent_id, key)
        await self._redis.delete(self._ns, full_key)

    # ── List keys ───────────────────────────────────────────────────────

    async def list_keys(self, agent_id: str) -> list[str]:
        """
        List all keys stored for an agent.

        Uses Redis SCAN under the hood, returning just the suffix
        portion of each key (stripping namespace + agent prefix).
        """
        pattern = f"aadap:{self._ns.value}:{agent_id}:*"
        prefix = f"aadap:{self._ns.value}:{agent_id}:"
        keys: list[str] = []
        cursor = 0
        while True:
            cursor, batch = await self._redis.raw.scan(
                cursor=cursor, match=pattern, count=100
            )
            for k in batch:
                key_str = k.decode("utf-8") if isinstance(k, bytes) else k
                # Strip the full prefix to return only the logical key
                if key_str.startswith(prefix):
                    keys.append(key_str[len(prefix):])
            if cursor == 0:
                break
        return keys
