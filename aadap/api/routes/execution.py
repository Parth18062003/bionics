"""
AADAP — Execution API Routes
===============================
REST endpoints for triggering and monitoring end-to-end task execution.

Architecture layer: L6 (Presentation).

Usage:
    POST /api/v1/tasks/{task_id}/execute  — Trigger full pipeline execution via LangGraph
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
from aadap.db.models import Execution, Task
from aadap.orchestrator import run_task_graph, replay, TaskState
from aadap.orchestrator.graph import _holder

logger = get_logger(__name__)

router = APIRouter(tags=["execution"])


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
    routing_decision: dict[str, Any] | None = None
    final_state: str | None = None


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


@router.post(
    "/api/v1/tasks/{task_id}/execute",
    response_model=ExecutionTriggerResponse,
    summary="Execute a task end-to-end via LangGraph",
    description=(
        "Triggers the full execution pipeline using LangGraph orchestration: "
        "routing → code generation → safety analysis → optimization → approval → platform execution."
    ),
)
async def execute_task(
    task_id: uuid.UUID,
    correlation_id: str | None = Depends(get_correlation_id),
    current_user: str | None = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ExecutionTriggerResponse:
    """
    Trigger end-to-end task execution via LangGraph.

    Uses the compiled LangGraph StateGraph for orchestration:
    - Routes task to appropriate agent (developer, ingestion, etl_pipeline, etc.)
    - Generates code via LLM
    - Runs safety analysis (static + semantic)
    - Runs optimization
    - Requests approval if needed
    - Executes on Databricks or Fabric
    """
    logger.info(
        "api.execution.trigger",
        task_id=str(task_id),
        correlation_id=correlation_id,
        user=current_user,
    )

    try:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        initial_metadata = {
            "title": task.title,
            "description": task.description,
            "environment": task.environment,
            "platform": (task.metadata_ or {}).get("platform", "databricks"),
            "language": (task.metadata_ or {}).get("language", "python"),
            "token_budget": task.token_budget,
            **(task.metadata_ or {}),
        }

        graph_result = await run_task_graph(task_id, initial_metadata)

        agent_result = graph_result.get("agent_result") or {}
        routing_decision = graph_result.get("routing_decision")

        return ExecutionTriggerResponse(
            task_id=str(task_id),
            status=graph_result.get("final_state", "UNKNOWN"),
            message=_get_status_message(graph_result.get("final_state")),
            output=agent_result.get("output") if isinstance(agent_result.get("output"), str) else None,
            error=graph_result.get("error"),
            code=graph_result.get("code"),
            language=initial_metadata.get("language"),
            job_id=agent_result.get("job_id") if isinstance(agent_result, dict) else None,
            duration_ms=agent_result.get("duration_ms") if isinstance(agent_result, dict) else None,
            routing_decision=routing_decision,
            final_state=graph_result.get("final_state"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "api.execution.error",
            task_id=str(task_id),
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=str(exc))


def _get_status_message(final_state: str | None) -> str:
    """Return a human-readable message for the final state."""
    messages = {
        "COMPLETED": "Task executed successfully.",
        "CANCELLED": "Task was cancelled.",
        "DEV_FAILED": "Development phase failed.",
        "VALIDATION_FAILED": "Code validation failed.",
        "APPROVAL_PENDING": "Task is awaiting approval.",
        "REJECTED": "Task was rejected.",
    }
    return messages.get(final_state or "", "Task execution completed.")


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


@router.get(
    "/api/v1/tasks/{task_id}/status",
    summary="Get current task status from LangGraph",
)
async def get_task_status(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get the current state of a task from the LangGraph state machine."""
    try:
        current_state = await replay(task_id)
        return {
            "task_id": str(task_id),
            "current_state": current_state.value,
            "is_terminal": current_state.value in {"COMPLETED", "CANCELLED", "REJECTED", "DEV_FAILED", "VALIDATION_FAILED"},
        }
    except Exception as exc:
        logger.error("api.status.error", task_id=str(task_id), error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))
