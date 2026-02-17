"""
Phase 2 Tests — Checkpoint Persistence
=========================================
Validates:
- Save checkpoint, load returns same state
- After simulated crash (Redis cleared), fallback to DB replay works
- Delete checkpoint removes from Redis
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aadap.orchestrator.checkpoints import Checkpoint, CheckpointManager
from aadap.orchestrator.events import EventStore
from aadap.orchestrator.state_machine import TaskState


# ── Helpers ─────────────────────────────────────────────────────────────



class _FakeMemoryStore:
    """In-memory Store mock for checkpoint tests."""

    def __init__(self):
        self._store: dict[str, bytes] = {}
        # Add set method alias for set_with_ttl compatibility if needed by some internal logic, 
        # but CheckpointManager uses set_with_ttl.
        
    async def set_with_ttl(self, ns, key, value, ttl=None):
        full_key = f"{ns}:{key}"
        self._store[full_key] = value.encode() if isinstance(value, str) else value

    async def get(self, ns, key) -> bytes | None:
        full_key = f"{ns}:{key}"
        return self._store.get(full_key)

    async def delete(self, ns, key) -> int:
        full_key = f"{ns}:{key}"
        if full_key in self._store:
            del self._store[full_key]
            return 1
        return 0


def _make_transition_row(task_id, from_state, to_state, seq_num):
    row = MagicMock()
    row.task_id = task_id
    row.from_state = from_state
    row.to_state = to_state
    row.sequence_num = seq_num
    row.created_at = datetime.now(timezone.utc)
    return row


# ── Tests ───────────────────────────────────────────────────────────────


class TestCheckpointSaveLoad:
    """Basic save/load cycle."""

    @pytest.fixture
    def store(self):
        return _FakeMemoryStore()

    @pytest.fixture
    def event_store(self):
        store = MagicMock(spec=EventStore)
        store.get_history = AsyncMock(return_value=[])
        return store

    @pytest.fixture
    def manager(self, store, event_store):
        return CheckpointManager(client=store, event_store=event_store)

    async def test_save_and_load(self, manager):
        """Saved checkpoint is recoverable via load."""
        task_id = uuid.uuid4()

        saved = await manager.save_checkpoint(
            task_id=task_id,
            state=TaskState.PLANNING,
            sequence_num=3,
            metadata={"key": "value"},
        )

        loaded = await manager.load_checkpoint(task_id)

        assert loaded is not None
        assert loaded.state == "PLANNING"
        assert loaded.sequence_num == 3
        assert loaded.metadata == {"key": "value"}
        assert loaded.task_id == str(task_id)

    async def test_load_missing_returns_none(self, store, event_store):
        """Loading a nonexistent checkpoint (with no history) returns None."""
        event_store.get_history = AsyncMock(return_value=[])
        manager = CheckpointManager(client=store, event_store=event_store)

        result = await manager.load_checkpoint(uuid.uuid4())
        assert result is None


class TestCheckpointCrashRecovery:
    """Simulate crash (Store emptied) and verify DB fallback."""

    async def test_replay_after_crash(self):
        """After Store is cleared, checkpoint is rebuilt from DB events."""
        task_id = uuid.uuid4()
        store = _FakeMemoryStore()

        # Simulate event history in DB
        history = [
            _make_transition_row(task_id, "SUBMITTED", "PARSING", 1),
            _make_transition_row(task_id, "PARSING", "PARSED", 2),
            _make_transition_row(task_id, "PARSED", "PLANNING", 3),
        ]
        event_store = MagicMock(spec=EventStore)
        event_store.get_history = AsyncMock(return_value=history)

        manager = CheckpointManager(client=store, event_store=event_store)

        # Save checkpoint
        await manager.save_checkpoint(task_id, TaskState.PLANNING, 3)

        # Simulate crash: clear Store
        store._store.clear()

        # Load should fall back to DB replay
        loaded = await manager.load_checkpoint(task_id)

        assert loaded is not None
        assert loaded.state == "PLANNING"
        assert loaded.sequence_num == 3

    async def test_redis_re_warmed_after_fallback(self):
        """After DB fallback, the checkpoint is written back to Store."""
        task_id = uuid.uuid4()
        store = _FakeMemoryStore()

        history = [
            _make_transition_row(task_id, "SUBMITTED", "PARSING", 1),
        ]
        event_store = MagicMock(spec=EventStore)
        event_store.get_history = AsyncMock(return_value=history)

        manager = CheckpointManager(client=store, event_store=event_store)

        # Store is empty — fallback will trigger
        loaded = await manager.load_checkpoint(task_id)
        assert loaded is not None

        # Second load should hit Store (no more DB call)
        event_store.get_history.reset_mock()
        loaded2 = await manager.load_checkpoint(task_id)
        assert loaded2 is not None
        # DB should NOT have been called again
        event_store.get_history.assert_not_called()


class TestCheckpointDelete:
    """Verify deletion."""

    async def test_delete_removes_from_store(self):
        """After delete, load returns None (falls back to empty DB)."""
        task_id = uuid.uuid4()
        store = _FakeMemoryStore()
        event_store = MagicMock(spec=EventStore)
        event_store.get_history = AsyncMock(return_value=[])

        manager = CheckpointManager(client=store, event_store=event_store)

        await manager.save_checkpoint(task_id, TaskState.SUBMITTED, 0)
        await manager.delete_checkpoint(task_id)

        loaded = await manager.load_checkpoint(task_id)
        assert loaded is None


class TestCheckpointSerialization:
    """Verify Checkpoint JSON round-trip."""

    def test_json_round_trip(self):
        cp = Checkpoint(
            task_id="abc-123",
            state="PLANNING",
            sequence_num=5,
            metadata={"foo": "bar"},
            created_at="2026-01-01T00:00:00+00:00",
        )
        raw = cp.to_json()
        restored = Checkpoint.from_json(raw)
        assert restored == cp
