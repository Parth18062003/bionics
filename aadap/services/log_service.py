"""
AADAP — Log Service
====================
Service for querying, filtering, and exporting task logs.

Architecture layer: L5 (Orchestration).

Provides structured log visibility for debugging and monitoring tasks.
Supports filtering by task, level, text search, and time range.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aadap.core.logging import get_logger
from aadap.db.models import TaskLog

logger = get_logger(__name__)


def _utcnow() -> datetime:
    """Return current UTC datetime with timezone."""
    return datetime.now(timezone.utc)


# ── Query Parameters ─────────────────────────────────────────────────────────


class LogQueryParams(BaseModel):
    """Parameters for querying logs."""

    task_id: uuid.UUID | None = None
    levels: list[str] | None = None
    search: str | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    start_time: datetime | None = None
    end_time: datetime | None = None


# ── Log Service ─────────────────────────────────────────────────────────────


class LogService:
    """
    Service for querying and managing task logs.
    
    Provides filtering, search, and export capabilities for the
    TaskLog table. Used by the API layer for log endpoints.
    """

    async def get_logs(
        self,
        params: LogQueryParams,
        db: AsyncSession,
    ) -> list[TaskLog]:
        """
        Query logs with filters.
        
        Args:
            params: Query parameters for filtering
            db: Database session
        
        Returns:
            List of TaskLog entries matching the filters
        """
        query = select(TaskLog)

        # Apply filters
        conditions = []

        if params.task_id:
            conditions.append(TaskLog.task_id == params.task_id)

        if params.levels:
            conditions.append(TaskLog.level.in_(params.levels))

        if params.search:
            # Case-insensitive text search in message
            search_pattern = f"%{params.search}%"
            conditions.append(TaskLog.message.ilike(search_pattern))

        if params.start_time:
            conditions.append(TaskLog.created_at >= params.start_time)

        if params.end_time:
            conditions.append(TaskLog.created_at <= params.end_time)

        if conditions:
            query = query.where(and_(*conditions))

        # Order by timestamp descending (newest first)
        query = query.order_by(desc(TaskLog.created_at))

        # Apply pagination
        query = query.limit(params.limit).offset(params.offset)

        result = await db.execute(query)
        logs = result.scalars().all()

        logger.debug(
            "log_service.get_logs",
            task_id=str(params.task_id) if params.task_id else None,
            levels=params.levels,
            search=params.search,
            count=len(logs),
        )

        return list(logs)

    async def get_log_count(
        self,
        params: LogQueryParams,
        db: AsyncSession,
    ) -> int:
        """
        Count logs matching the filters.
        
        Args:
            params: Query parameters for filtering
            db: Database session
        
        Returns:
            Total count of matching logs
        """
        query = select(func.count(TaskLog.id))

        # Apply same filters as get_logs
        conditions = []

        if params.task_id:
            conditions.append(TaskLog.task_id == params.task_id)

        if params.levels:
            conditions.append(TaskLog.level.in_(params.levels))

        if params.search:
            search_pattern = f"%{params.search}%"
            conditions.append(TaskLog.message.ilike(search_pattern))

        if params.start_time:
            conditions.append(TaskLog.created_at >= params.start_time)

        if params.end_time:
            conditions.append(TaskLog.created_at <= params.end_time)

        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        count = result.scalar() or 0

        return count

    async def get_logs_by_correlation(
        self,
        correlation_id: str,
        db: AsyncSession,
    ) -> list[TaskLog]:
        """
        Get all logs with the same correlation ID.
        
        Useful for tracing related events across agents/services.
        
        Args:
            correlation_id: The correlation ID to filter by
            db: Database session
        
        Returns:
            List of TaskLog entries with matching correlation_id
        """
        query = (
            select(TaskLog)
            .where(TaskLog.correlation_id == correlation_id)
            .order_by(TaskLog.created_at)
        )

        result = await db.execute(query)
        logs = result.scalars().all()

        logger.debug(
            "log_service.get_logs_by_correlation",
            correlation_id=correlation_id,
            count=len(logs),
        )

        return list(logs)

    async def get_recent_logs(
        self,
        task_id: uuid.UUID,
        limit: int,
        db: AsyncSession,
    ) -> list[TaskLog]:
        """
        Get the most recent logs for a task.
        
        Quick method for embedded view in task detail page.
        
        Args:
            task_id: Task ID to filter by
            limit: Maximum number of logs to return
            db: Database session
        
        Returns:
            List of most recent TaskLog entries for the task
        """
        query = (
            select(TaskLog)
            .where(TaskLog.task_id == task_id)
            .order_by(desc(TaskLog.created_at))
            .limit(limit)
        )

        result = await db.execute(query)
        logs = result.scalars().all()

        return list(logs)

    async def export_logs(
        self,
        params: LogQueryParams,
        format: str,
        db: AsyncSession,
    ) -> str:
        """
        Export logs as JSON or CSV.
        
        Args:
            params: Query parameters for filtering
            format: Export format ('json' or 'csv')
            db: Database session
        
        Returns:
            String containing the exported data
        """
        # Get all matching logs (no pagination for export)
        export_params = LogQueryParams(
            task_id=params.task_id,
            levels=params.levels,
            search=params.search,
            limit=10000,  # Max export limit
            offset=0,
            start_time=params.start_time,
            end_time=params.end_time,
        )

        logs = await self.get_logs(export_params, db)

        if format == "json":
            return self._export_json(logs)
        elif format == "csv":
            return self._export_csv(logs)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _export_json(self, logs: list[TaskLog]) -> str:
        """Export logs as JSON."""
        data = [
            {
                "id": str(log.id),
                "task_id": str(log.task_id),
                "timestamp": log.created_at.isoformat(),
                "level": log.level,
                "message": log.message,
                "correlation_id": log.correlation_id,
                "source": log.source,
            }
            for log in logs
        ]
        return json.dumps(data, indent=2)

    def _export_csv(self, logs: list[TaskLog]) -> str:
        """Export logs as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["id", "task_id", "timestamp", "level", "message", "correlation_id", "source"])

        # Data rows
        for log in logs:
            writer.writerow([
                str(log.id),
                str(log.task_id),
                log.created_at.isoformat(),
                log.level,
                log.message,
                log.correlation_id or "",
                log.source or "",
            ])

        return output.getvalue()


# ── Log Emission Helper ──────────────────────────────────────────────────────


async def emit_log(
    task_id: uuid.UUID,
    level: str,
    message: str,
    db: AsyncSession,
    correlation_id: str | None = None,
    source: str | None = None,
) -> TaskLog:
    """
    Emit a structured log entry to the TaskLog table.
    
    This is the primary function for agents and services to emit
    logs that are visible in the UI.
    
    Args:
        task_id: The task this log belongs to
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        message: Log message content
        db: Database session
        correlation_id: Optional correlation ID for tracing
        source: Optional source (agent/service name)
    
    Returns:
        The created TaskLog entry
    """
    log = TaskLog(
        task_id=task_id,
        level=level,
        message=message,
        correlation_id=correlation_id,
        source=source,
        created_at=_utcnow(),
    )

    db.add(log)
    await db.flush()  # Get the ID without committing

    logger.debug(
        "log_service.emit_log",
        task_id=str(task_id),
        level=level,
        source=source,
    )

    return log


# ── Singleton Instance ───────────────────────────────────────────────────────

_log_service: LogService | None = None


def get_log_service() -> LogService:
    """Get the global log service instance."""
    global _log_service
    if _log_service is None:
        _log_service = LogService()
    return _log_service
