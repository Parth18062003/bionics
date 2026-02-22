"""
AADAP — Log API Routes
=========================
REST endpoints for log visibility and debugging.

Architecture layer: L6 (Presentation).
Phase 3 contract: Real-time task logging and observability.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from aadap.api.deps import get_session
from aadap.core.logging import get_logger
from aadap.db.models import TaskLog
from aadap.services.log_service import get_log_service, LogQueryParams

logger = get_logger(__name__)

router = APIRouter(prefix="/api/logs", tags=["logs"])


# ── Response Schemas ────────────────────────────────────────────────────────


class LogResponse(BaseModel):
    """Response for single log entry."""
    id: str
    task_id: str
    timestamp: str
    level: str
    message: str
    correlation_id: str | None = None
    source: str | None = None


class LogsListResponse(BaseModel):
    """Response for logs list."""
    logs: list[LogResponse]
    total: int
    limit: int
    offset: int


# ── Helpers ─────────────────────────────────────────────────────────────────


def _log_to_response(log: TaskLog) -> LogResponse:
    """Convert TaskLog to response schema."""
    return LogResponse(
        id=str(log.id),
        task_id=str(log.task_id),
        timestamp=log.created_at.isoformat() if log.created_at else "",
        level=log.level,
        message=log.message,
        correlation_id=log.correlation_id,
        source=log.source,
    )


def _parse_levels(levels_str: str | None) -> list[str] | None:
    """Parse comma-separated levels string into list."""
    if not levels_str:
        return None
    return [l.strip().upper() for l in levels_str.split(",") if l.strip()]


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("", response_model=LogsListResponse)
async def get_logs(
    task_id: uuid.UUID | None = Query(None, description="Filter by task ID"),
    levels: str | None = Query(None, description="Filter by levels (comma-separated: DEBUG,INFO,WARNING,ERROR)"),
    search: str | None = Query(None, description="Search in message content"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    start_time: datetime | None = Query(None, description="Filter from this time (ISO format)"),
    end_time: datetime | None = Query(None, description="Filter to this time (ISO format)"),
    db: AsyncSession = Depends(get_session),
) -> LogsListResponse:
    """
    Query logs with filters.
    
    Supports:
    - Filter by task
    - Filter by multiple log levels
    - Text search in message
    - Time range filtering
    - Pagination
    """
    service = get_log_service()
    
    params = LogQueryParams(
        task_id=task_id,
        levels=_parse_levels(levels),
        search=search,
        limit=limit,
        offset=offset,
        start_time=start_time,
        end_time=end_time,
    )
    
    logs = await service.get_logs(params, db)
    total = await service.get_log_count(params, db)
    
    return LogsListResponse(
        logs=[_log_to_response(log) for log in logs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/correlation/{correlation_id}", response_model=LogsListResponse)
async def get_logs_by_correlation(
    correlation_id: str,
    db: AsyncSession = Depends(get_session),
) -> LogsListResponse:
    """
    Get all logs with the same correlation ID.
    
    Useful for tracing related events across agents and services.
    """
    service = get_log_service()
    
    logs = await service.get_logs_by_correlation(correlation_id, db)
    
    if not logs:
        raise HTTPException(status_code=404, detail="No logs found with this correlation ID")
    
    return LogsListResponse(
        logs=[_log_to_response(log) for log in logs],
        total=len(logs),
        limit=len(logs),
        offset=0,
    )


@router.get("/export")
async def export_logs(
    task_id: uuid.UUID | None = Query(None, description="Filter by task ID"),
    levels: str | None = Query(None, description="Filter by levels (comma-separated)"),
    search: str | None = Query(None, description="Search in message content"),
    start_time: datetime | None = Query(None, description="Filter from this time"),
    end_time: datetime | None = Query(None, description="Filter to this time"),
    format: str = Query("json", description="Export format: json or csv"),
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """
    Export logs as JSON or CSV file.
    
    Returns a file download with the exported data.
    """
    service = get_log_service()
    
    params = LogQueryParams(
        task_id=task_id,
        levels=_parse_levels(levels),
        search=search,
        limit=10000,  # Higher limit for export
        offset=0,
        start_time=start_time,
        end_time=end_time,
    )
    
    content = await service.export_logs(params, format, db)
    
    # Determine content type and filename
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"logs-{ts}.{format}"
    content_type = "application/json" if format == "json" else "text/csv"
    
    logger.info("logs_api.export_logs", format=format, filename=filename)
    
    async def stream():
        yield content
    
    return StreamingResponse(
        stream(),
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


# ── Task-specific endpoint for embedded view ────────────────────────────────
# Note: This uses a different prefix to be accessible at /api/tasks/{id}/logs


task_logs_router = APIRouter(prefix="/api/tasks", tags=["logs"])


@task_logs_router.get("/{task_id}/logs", response_model=LogsListResponse)
async def get_task_logs(
    task_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    db: AsyncSession = Depends(get_session),
) -> LogsListResponse:
    """
    Get recent logs for a specific task.
    
    This is the minimal embedded view for task detail pages.
    No filtering or search - just recent logs for the task.
    """
    service = get_log_service()
    
    logs = await service.get_recent_logs(task_id, limit, db)
    
    # Get total count for this task
    params = LogQueryParams(task_id=task_id, limit=1, offset=0)
    total = await service.get_log_count(params, db)
    
    logger.debug("logs_api.get_task_logs", task_id=str(task_id), count=len(logs))
    
    return LogsListResponse(
        logs=[_log_to_response(log) for log in logs],
        total=total,
        limit=limit,
        offset=0,
    )
