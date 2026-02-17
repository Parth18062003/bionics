"""
AADAP — Checkpoint Persistence
================================
Save and restore task state checkpoints using in-memory store (fast)
with DB event replay as fallback (crash recovery).

Architecture layer: L5 (Orchestration) + L2 (Memory: CHECKPOINTS).

Usage:
    mgr = CheckpointManager(memory_client, event_store)
    await mgr.save_checkpoint(task_id, state, seq_num, metadata)
    cp = await mgr.load_checkpoint(task_id)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from aadap.core.memory_store import MemoryStoreClient, MemoryNamespace
from aadap.orchestrator.events import EventStore
from aadap.orchestrator.state_machine import TaskState


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """Immutable snapshot of task state at a point in time."""

    task_id: str
    state: str
    sequence_num: int
    metadata: dict
    created_at: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str | bytes) -> Checkpoint:
        data = json.loads(raw)
        return cls(**data)


class CheckpointManager:
    """
    Two-tier checkpoint persistence.

    - **Primary**: In-memory CHECKPOINTS namespace (low-latency).
    - **Fallback**: DB event replay via ``EventStore`` (crash recovery).

    After a simulated crash (store cleared), ``load_checkpoint``
    transparently replays from DB to rebuild consistent state.
    """

    _KEY_PREFIX = "task"

    def __init__(
        self,
        client: MemoryStoreClient,
        event_store: EventStore,
    ) -> None:
        self._client = client
        self._event_store = event_store

    def _memory_key(self, task_id: uuid.UUID) -> str:
        return f"{self._KEY_PREFIX}:{task_id}"

    async def save_checkpoint(
        self,
        task_id: uuid.UUID,
        state: TaskState,
        sequence_num: int,
        metadata: dict | None = None,
    ) -> Checkpoint:
        """
        Persist a checkpoint to the CHECKPOINTS namespace.

        Returns the saved ``Checkpoint``.
        """
        cp = Checkpoint(
            task_id=str(task_id),
            state=state.value,
            sequence_num=sequence_num,
            metadata=metadata or {},
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        await self._client.set_with_ttl(
            MemoryNamespace.CHECKPOINTS,
            self._memory_key(task_id),
            cp.to_json(),
        )
        return cp

    async def load_checkpoint(
        self, task_id: uuid.UUID
    ) -> Checkpoint | None:
        """
        Load checkpoint from cache.  Falls back to DB replay on miss.

        This ensures crash recovery: if the in-memory store was cleared,
        the event store is replayed to rebuild the checkpoint.
        """
        raw = await self._client.get(
            MemoryNamespace.CHECKPOINTS,
            self._memory_key(task_id),
        )
        if raw is not None:
            return Checkpoint.from_json(raw)

        # Fallback: replay from DB event store
        return await self._replay_from_db(task_id)

    async def delete_checkpoint(self, task_id: uuid.UUID) -> None:
        """Remove checkpoint from the store."""
        await self._client.delete(
            MemoryNamespace.CHECKPOINTS,
            self._memory_key(task_id),
        )

    async def _replay_from_db(
        self, task_id: uuid.UUID
    ) -> Checkpoint | None:
        """
        Rebuild checkpoint by replaying the full event history from DB.

        Returns ``None`` if the task has no transitions at all.
        """
        history = await self._event_store.get_history(task_id)
        if not history:
            return None

        last = history[-1]
        cp = Checkpoint(
            task_id=str(task_id),
            state=last.to_state,
            sequence_num=last.sequence_num,
            metadata={},
            created_at=last.created_at.isoformat()
            if isinstance(last.created_at, datetime)
            else str(last.created_at),
        )

        # Re-warm in-memory cache
        await self._client.set_with_ttl(
            MemoryNamespace.CHECKPOINTS,
            self._memory_key(task_id),
            cp.to_json(),
        )
        return cp
