"""
Phase 2 Tests — Event Sourcing
=================================
Validates:
- Transition recording creates DB rows
- Replay derives correct final state
- Sequence numbers are strictly monotonic
- Audit events created on each transition (INV-06)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aadap.orchestrator.events import EventStore
from aadap.orchestrator.state_machine import (
    InvalidTransitionError,
    TaskState,
)


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_transition_row(
    task_id: uuid.UUID,
    from_state: str,
    to_state: str,
    seq_num: int,
) -> MagicMock:
    """Create a mock StateTransition row."""
    row = MagicMock()
    row.task_id = task_id
    row.from_state = from_state
    row.to_state = to_state
    row.sequence_num = seq_num
    row.triggered_by = "system"
    row.reason = None
    row.metadata_ = {}
    row.created_at = datetime.now(timezone.utc)
    return row


class _FakeSession:
    """Minimal fake session for testing EventStore without a real DB."""

    def __init__(self):
        self.added: list = []
        self.executed: list = []
        self._transitions: list = []
        self._seq_result = MagicMock()
        self._seq_result.scalar_one.return_value = 0

    def add(self, obj):
        self.added.append(obj)

    async def execute(self, stmt):
        self.executed.append(stmt)
        # For sequence number query
        return self._seq_result

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


# ── Tests ───────────────────────────────────────────────────────────────


class TestRecordTransition:
    """Verify transition recording."""

    @pytest.fixture
    def session(self):
        return _FakeSession()

    @pytest.fixture
    def event_store(self, session):
        def factory():
            return session
        return EventStore(factory)

    async def test_records_transition_and_audit(self, event_store, session):
        """Recording a transition creates both a StateTransition and AuditEvent row."""
        task_id = uuid.uuid4()

        result = await event_store.record_transition(
            task_id=task_id,
            from_state=TaskState.SUBMITTED,
            to_state=TaskState.PARSING,
            triggered_by="test_user",
            reason="Starting parse",
        )

        # Should have added 2 objects: StateTransition + AuditEvent
        assert len(session.added) == 2

        # First added is the StateTransition
        transition = session.added[0]
        assert transition.from_state == "SUBMITTED"
        assert transition.to_state == "PARSING"
        assert transition.sequence_num == 1
        assert transition.triggered_by == "test_user"
        assert transition.reason == "Starting parse"

        # Second added is the AuditEvent (INV-06)
        audit = session.added[1]
        assert audit.event_type == "state.transition"
        assert audit.actor == "test_user"

    async def test_rejects_invalid_transition(self, event_store):
        """An invalid transition raises before any DB write."""
        task_id = uuid.uuid4()
        with pytest.raises(InvalidTransitionError):
            await event_store.record_transition(
                task_id=task_id,
                from_state=TaskState.SUBMITTED,
                to_state=TaskState.DEPLOYED,  # Invalid
            )

    async def test_sequence_numbers_increment(self, session):
        """Successive transitions get increasing sequence numbers."""

        class _TrackingSession(_FakeSession):
            """Session that returns incrementing max(sequence_num) values."""

            def __init__(self):
                super().__init__()
                self._seq_counter = 0

            async def execute(self, stmt):
                # Detect the max() query vs. UPDATE by checking if it's
                # a select (returns scalar) or update (returns nothing useful).
                result = MagicMock()
                stmt_str = str(stmt)
                if "max" in stmt_str.lower() or "coalesce" in stmt_str.lower():
                    result.scalar_one.return_value = self._seq_counter
                    self._seq_counter += 1
                return result

        tracking = _TrackingSession()

        def factory():
            return tracking

        store = EventStore(factory)
        task_id = uuid.uuid4()

        await store.record_transition(
            task_id, TaskState.SUBMITTED, TaskState.PARSING
        )
        first_transition = tracking.added[0]
        assert first_transition.sequence_num == 1

        await store.record_transition(
            task_id, TaskState.PARSING, TaskState.PARSED
        )
        second_transition = tracking.added[2]  # index 2 (0=trans, 1=audit, 2=trans)
        assert second_transition.sequence_num == 2
        assert second_transition.sequence_num > first_transition.sequence_num


class TestReplay:
    """Verify state replay from event history."""

    async def test_replay_no_history_returns_submitted(self):
        """A task with no transitions replays to SUBMITTED."""
        mock_session = _FakeSession()

        async def factory():
            return mock_session

        # Patch get_history to return empty
        store = EventStore(factory)
        with patch.object(store, "get_history", new_callable=AsyncMock, return_value=[]):
            result = await store.replay(uuid.uuid4())
        assert result == TaskState.SUBMITTED

    async def test_replay_returns_last_to_state(self):
        """Replay returns the to_state of the last transition."""
        task_id = uuid.uuid4()
        history = [
            _make_transition_row(task_id, "SUBMITTED", "PARSING", 1),
            _make_transition_row(task_id, "PARSING", "PARSED", 2),
            _make_transition_row(task_id, "PARSED", "PLANNING", 3),
        ]

        store = EventStore(lambda: _FakeSession())
        with patch.object(store, "get_history", new_callable=AsyncMock, return_value=history):
            result = await store.replay(task_id)
        assert result == TaskState.PLANNING

    async def test_replay_with_retries(self):
        """Replay handles retry loops (DEV_FAILED → IN_DEVELOPMENT)."""
        task_id = uuid.uuid4()
        history = [
            _make_transition_row(task_id, "SUBMITTED", "PARSING", 1),
            _make_transition_row(task_id, "PARSING", "PARSED", 2),
            _make_transition_row(task_id, "PARSED", "PLANNING", 3),
            _make_transition_row(task_id, "PLANNING", "PLANNED", 4),
            _make_transition_row(task_id, "PLANNED", "AGENT_ASSIGNMENT", 5),
            _make_transition_row(task_id, "AGENT_ASSIGNMENT", "AGENT_ASSIGNED", 6),
            _make_transition_row(task_id, "AGENT_ASSIGNED", "IN_DEVELOPMENT", 7),
            _make_transition_row(task_id, "IN_DEVELOPMENT", "DEV_FAILED", 8),
            _make_transition_row(task_id, "DEV_FAILED", "IN_DEVELOPMENT", 9),  # retry
            _make_transition_row(task_id, "IN_DEVELOPMENT", "CODE_GENERATED", 10),
        ]

        store = EventStore(lambda: _FakeSession())
        with patch.object(store, "get_history", new_callable=AsyncMock, return_value=history):
            result = await store.replay(task_id)
        assert result == TaskState.CODE_GENERATED
