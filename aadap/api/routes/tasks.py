"""
AADAP — Task API Routes
==========================
REST endpoints for task lifecycle management.

Architecture layer: L6 (Presentation).
Phase 7 contract: Task submission, Task status dashboard.

Invariant enforcement:
- UI cannot bypass API (architectural — frontend calls these endpoints)
- API cannot bypass orchestrator (all mutations via ``graph.*`` functions)
- INV-02: Transitions persisted atomically (via ``graph.transition``)
- INV-06: Audit trail recorded on every transition (via ``EventStore``)
- Correlation ID propagated (``CorrelationMiddleware`` + ``X-Correlation-ID``)

Usage:
    POST   /api/v1/tasks                     — Submit task
    GET    /api/v1/tasks                      — List tasks
    GET    /api/v1/tasks/{task_id}            — Get task detail
    POST   /api/v1/tasks/{task_id}/transition — Trigger transition
    GET    /api/v1/tasks/{task_id}/events     — Get event/transition stream
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aadap.api.deps import get_correlation_id, get_current_user, get_session
from aadap.core.logging import get_logger
from aadap.db.models import (
    AuditEvent,
    StateTransition,
    Task,
    TASK_STATES,
)
from aadap.orchestrator.graph import create_task, replay, transition
from aadap.orchestrator.state_machine import InvalidTransitionError

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


# ── Request / Response Schemas ──────────────────────────────────────────


class TaskCreateRequest(BaseModel):
    """Request body for task creation."""

    title: str = Field(..., min_length=1, max_length=512)
    description: str | None = None
    priority: int = Field(default=0, ge=0, le=10)
    environment: str = Field(default="SANDBOX", pattern=r"^(SANDBOX|PRODUCTION)$")


class TaskResponse(BaseModel):
    """Task summary returned by the API."""

    id: str
    title: str
    description: str | None
    current_state: str
    priority: int
    environment: str
    created_by: str | None
    token_budget: int
    tokens_used: int
    retry_count: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """Paginated task list."""

    tasks: list[TaskResponse]
    total: int
    page: int
    page_size: int


class TransitionRequest(BaseModel):
    """Request body for state transition."""

    next_state: str = Field(
        ...,
        description="Target state (must be in authoritative state set).",
    )
    reason: str | None = None


class TransitionResponse(BaseModel):
    """Response after a successful transition."""

    task_id: str
    from_state: str
    to_state: str
    triggered_by: str | None
    reason: str | None


class EventResponse(BaseModel):
    """Single state transition event."""

    id: str
    from_state: str
    to_state: str
    sequence_num: int
    triggered_by: str | None
    reason: str | None
    created_at: str


# ── Endpoints ───────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=TaskResponse,
    status_code=201,
    summary="Submit a new task",
    description="Creates a task in SUBMITTED state via the orchestrator.",
)
async def create_task_endpoint(
    body: TaskCreateRequest,
    session: AsyncSession = Depends(get_session),
    correlation_id: str | None = Depends(get_correlation_id),
    current_user: str = Depends(get_current_user),
) -> TaskResponse:
    """
    Submit a new task.

    Delegates to ``graph.create_task`` — the API never directly
    inserts into the database (invariant: API cannot bypass orchestrator).
    """
    task_id = await create_task(
        title=body.title,
        description=body.description,
        priority=body.priority,
        environment=body.environment,
        created_by=current_user,
    )

    logger.info(
        "api.task.created",
        task_id=str(task_id),
        correlation_id=correlation_id,
    )

    # Fetch the created task to return full details
    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=500, detail="Task creation failed.")

    return _task_to_response(task)


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List tasks",
    description="Paginated task list with optional state filter.",
)
async def list_tasks(
    state: str | None = Query(None, description="Filter by state"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> TaskListResponse:
    """List tasks with pagination."""
    query = select(Task)
    count_query = select(func.count(Task.id))

    if state is not None:
        state_upper = state.upper()
        if state_upper not in TASK_STATES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid state '{state}'. Must be one of {TASK_STATES}",
            )
        query = query.where(Task.current_state == state_upper)
        count_query = count_query.where(Task.current_state == state_upper)

    # Total count
    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    # Page
    offset = (page - 1) * page_size
    query = query.order_by(Task.created_at.desc()).offset(offset).limit(page_size)
    result = await session.execute(query)
    tasks = result.scalars().all()

    return TaskListResponse(
        tasks=[_task_to_response(t) for t in tasks],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get task detail",
)
async def get_task(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """Get a single task by ID."""
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return _task_to_response(task)


@router.post(
    "/{task_id}/transition",
    response_model=TransitionResponse,
    summary="Trigger state transition",
    description="Transitions a task to the next state via the orchestrator.",
)
async def transition_task(
    task_id: uuid.UUID,
    body: TransitionRequest,
    correlation_id: str | None = Depends(get_correlation_id),
    current_user: str = Depends(get_current_user),
) -> TransitionResponse:
    """
    Trigger a state transition.

    Delegates to ``graph.transition``, which runs all guards,
    records the event atomically (INV-02), and writes the
    audit trail (INV-06).
    """
    try:
        current_state = await replay(task_id)
        new_state = await transition(
            task_id=task_id,
            next_state=body.next_state,
            triggered_by=current_user,
            reason=body.reason,
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error(
            "api.task.transition_failed",
            task_id=str(task_id),
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail="Transition failed.")

    logger.info(
        "api.task.transitioned",
        task_id=str(task_id),
        to_state=new_state.value,
        correlation_id=correlation_id,
    )

    return TransitionResponse(
        task_id=str(task_id),
        from_state=current_state.value,
        to_state=new_state.value,
        triggered_by=current_user,
        reason=body.reason,
    )


@router.get(
    "/{task_id}/events",
    response_model=list[EventResponse],
    summary="Get task event stream",
    description="Returns all state transitions for a task, ordered by sequence.",
)
async def get_task_events(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[EventResponse]:
    """Get the transition history for a task (real-time polling support)."""
    result = await session.execute(
        select(StateTransition)
        .where(StateTransition.task_id == task_id)
        .order_by(StateTransition.sequence_num)
    )
    transitions = result.scalars().all()

    return [
        EventResponse(
            id=str(t.id),
            from_state=t.from_state,
            to_state=t.to_state,
            sequence_num=t.sequence_num,
            triggered_by=t.triggered_by,
            reason=t.reason,
            created_at=t.created_at.isoformat() if t.created_at else "",
        )
        for t in transitions
    ]


# ── Helpers ─────────────────────────────────────────────────────────────


def _task_to_response(task: Task) -> TaskResponse:
    """Convert a Task ORM object to a TaskResponse."""
    return TaskResponse(
        id=str(task.id),
        title=task.title,
        description=task.description,
        current_state=task.current_state,
        priority=task.priority,
        environment=task.environment,
        created_by=task.created_by,
        token_budget=task.token_budget,
        tokens_used=task.tokens_used,
        retry_count=task.retry_count,
        created_at=task.created_at.isoformat() if task.created_at else "",
        updated_at=task.updated_at.isoformat() if task.updated_at else "",
    )
