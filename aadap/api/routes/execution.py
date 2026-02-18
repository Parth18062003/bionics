"""
AADAP — Execution API Routes
================================
REST endpoints for triggering and monitoring end-to-end task execution.

Architecture layer: L6 (Presentation).

Usage:
    POST /api/v1/tasks/{task_id}/execute  — Trigger full pipeline execution
    GET  /api/v1/executions/{task_id}     — Get execution records for a task
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aadap.api.deps import get_correlation_id, get_current_user, get_session
from aadap.core.logging import get_logger
from aadap.db.models import Execution
from aadap.services.execution import ExecutionService

logger = get_logger(__name__)

router = APIRouter(tags=["execution"])


# ── Response Schemas ────────────────────────────────────────────────────


class ExecutionTriggerResponse(BaseModel):
    """Response after triggering task execution."""

    task_id: str
    status: str
    message: str | None = None
    output: str | None = None
    error: str | None = None
    code: str | None = None
    language: str | None = None
    job_id: str | None = None
    duration_ms: int | None = None


class ExecutionRecordResponse(BaseModel):
    """An execution record from the database."""

    id: str
    task_id: str
    environment: str
    status: str
    output: str | None
    error: str | None
    duration_ms: int | None
    started_at: str | None
    completed_at: str | None
    created_at: str


# ── Module-level service ───────────────────────────────────────────────

_execution_service: ExecutionService | None = None


def _get_execution_service() -> ExecutionService:
    """Lazily initialize the execution service singleton."""
    global _execution_service
    if _execution_service is None:
        _execution_service = ExecutionService.create()
    return _execution_service


# ── Endpoints ───────────────────────────────────────────────────────────


@router.post(
    "/api/v1/tasks/{task_id}/execute",
    response_model=ExecutionTriggerResponse,
    summary="Execute a task end-to-end",
    description=(
        "Triggers the full execution pipeline: "
        "code generation → safety analysis → Databricks execution → result retrieval."
    ),
)
async def execute_task(
    task_id: uuid.UUID,
    correlation_id: str | None = Depends(get_correlation_id),
    current_user: str = Depends(get_current_user),
) -> ExecutionTriggerResponse:
    """
    Trigger end-to-end task execution.

    Delegates to ``ExecutionService.execute_task`` which drives the task
    through the full 25-state machine pipeline.
    """
    logger.info(
        "api.execution.trigger",
        task_id=str(task_id),
        correlation_id=correlation_id,
        user=current_user,
    )

    try:
        service = _get_execution_service()
        result = await service.execute_task(task_id)

        return ExecutionTriggerResponse(
            task_id=result.get("task_id", str(task_id)),
            status=result.get("status", "UNKNOWN"),
            message=result.get("message"),
            output=result.get("output"),
            error=result.get("error"),
            code=result.get("code"),
            language=result.get("language"),
            job_id=result.get("job_id"),
            duration_ms=result.get("duration_ms"),
        )
    except Exception as exc:
        logger.error(
            "api.execution.error",
            task_id=str(task_id),
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/api/v1/executions/{task_id}",
    response_model=list[ExecutionRecordResponse],
    summary="Get execution records for a task",
)
async def get_executions(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[ExecutionRecordResponse]:
    """Return all execution records for the given task."""
    result = await session.execute(
        select(Execution)
        .where(Execution.task_id == task_id)
        .order_by(Execution.created_at.desc())
    )
    executions = result.scalars().all()

    return [
        ExecutionRecordResponse(
            id=str(e.id),
            task_id=str(e.task_id),
            environment=e.environment,
            status=e.status,
            output=e.output,
            error=e.error,
            duration_ms=e.duration_ms,
            started_at=e.started_at.isoformat() if e.started_at else None,
            completed_at=e.completed_at.isoformat() if e.completed_at else None,
            created_at=e.created_at.isoformat() if e.created_at else "",
        )
        for e in executions
    ]
