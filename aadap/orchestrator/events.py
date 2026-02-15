"""
AADAP — Event Sourcing
========================
Immutable state transition records with audit trail.

Architecture layer: L5 (Orchestration).
Enforces:
- INV-02: All state transitions persisted before acknowledgment
- INV-06: Complete audit trail for all actions and decisions

Usage:
    store = EventStore(session_factory)
    await store.record_transition(task_id, from_state, to_state)
    history = await store.get_history(task_id)
    current = await store.replay(task_id)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aadap.db.models import AuditEvent, StateTransition, Task
from aadap.orchestrator.state_machine import TaskState, TaskStateMachine


class EventStore:
    """
    Append-only event store for task state transitions.

    Each transition is atomically persisted alongside a Task update
    and an AuditEvent, satisfying INV-02 and INV-06.
    """

    def __init__(self, session_factory: Callable[..., Any]) -> None:
        """
        Parameters
        ----------
        session_factory
            An async context manager that yields an ``AsyncSession``.
            Typically ``aadap.db.session.get_db_session``.
        """
        self._session_factory = session_factory

    async def record_transition(
        self,
        task_id: uuid.UUID,
        from_state: TaskState,
        to_state: TaskState,
        triggered_by: str | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> StateTransition:
        """
        Persist a state transition atomically.

        Steps (single transaction — INV-02):
        1. Validate transition via state machine
        2. Compute next sequence number
        3. Insert StateTransition row
        4. Update Task.current_state
        5. Insert AuditEvent row (INV-06)
        6. Commit

        Raises ``InvalidTransitionError`` if the transition is not in
        the authoritative whitelist.
        """
        TaskStateMachine.validate_transition(from_state, to_state)

        async with self._session_factory() as session:
            session: AsyncSession

            seq_num = await self._next_sequence_num(session, task_id)

            transition = StateTransition(
                id=uuid.uuid4(),
                task_id=task_id,
                from_state=from_state.value,
                to_state=to_state.value,
                sequence_num=seq_num,
                triggered_by=triggered_by,
                reason=reason,
                metadata_=metadata or {},
                created_at=datetime.now(timezone.utc),
            )
            session.add(transition)

            # Update task current state
            await session.execute(
                update(Task)
                .where(Task.id == task_id)
                .values(
                    current_state=to_state.value,
                    updated_at=datetime.now(timezone.utc),
                )
            )

            # INV-06: Audit trail
            audit = AuditEvent(
                id=uuid.uuid4(),
                task_id=task_id,
                event_type="state.transition",
                actor=triggered_by,
                action=f"{from_state.value} → {to_state.value}",
                resource_type="task",
                resource_id=str(task_id),
                details={
                    "from_state": from_state.value,
                    "to_state": to_state.value,
                    "sequence_num": seq_num,
                    "reason": reason,
                },
                created_at=datetime.now(timezone.utc),
            )
            session.add(audit)

            # Commit handled by session context manager (INV-02)
            return transition

    async def get_history(
        self, task_id: uuid.UUID
    ) -> list[StateTransition]:
        """Return all transitions for a task, ordered by sequence number."""
        async with self._session_factory() as session:
            session: AsyncSession
            result = await session.execute(
                select(StateTransition)
                .where(StateTransition.task_id == task_id)
                .order_by(StateTransition.sequence_num)
            )
            return list(result.scalars().all())

    async def replay(self, task_id: uuid.UUID) -> TaskState:
        """
        Replay all events to derive the current state.

        Returns the ``to_state`` of the last transition, or ``SUBMITTED``
        if no transitions exist (initial state).
        """
        history = await self.get_history(task_id)
        if not history:
            return TaskState.SUBMITTED
        return TaskStateMachine.parse_state(history[-1].to_state)

    async def get_next_sequence_num(
        self, task_id: uuid.UUID
    ) -> int:
        """Public accessor for the next sequence number."""
        async with self._session_factory() as session:
            return await self._next_sequence_num(session, task_id)

    @staticmethod
    async def _next_sequence_num(
        session: AsyncSession, task_id: uuid.UUID
    ) -> int:
        """Compute the next sequence number for the given task."""
        result = await session.execute(
            select(func.coalesce(func.max(StateTransition.sequence_num), 0))
            .where(StateTransition.task_id == task_id)
        )
        return result.scalar_one() + 1
