"""
AADAP — Health Endpoint
========================
Provides system health checks for DB and in-memory store connectivity.

Phase 1 DoD: "Health endpoint responds."
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from aadap.core.memory_store import get_memory_store
from aadap.db.session import get_engine

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    postgres: str
    redis: str  # Preserved for API backward compatibility (checks memory store)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description="Returns connectivity status for PostgreSQL and in-memory store.",
)
async def health_check() -> HealthResponse:
    """
    Health endpoint.

    Returns 200 with component-level status.
    Each component is 'ok' or 'error'.
    Overall status is 'healthy' only if all components are ok.
    """
    pg_status = await _check_postgres()
    memory_status = await _check_memory_store()

    overall = "healthy" if pg_status == "ok" and memory_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        postgres=pg_status,
        redis=memory_status,
    )


async def _check_postgres() -> str:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


async def _check_memory_store() -> str:
    try:
        store = await get_memory_store()
        if await store.ping():
            return "ok"
        return "error"
    except Exception:
        return "error"
