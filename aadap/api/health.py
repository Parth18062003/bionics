"""
AADAP — Health Endpoint
========================
Provides system health checks for DB and Redis connectivity.

Phase 1 DoD: "Health endpoint responds."
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from aadap.core.redis import get_redis
from aadap.db.session import get_engine

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str
    postgres: str
    redis: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description="Returns connectivity status for PostgreSQL and Redis.",
)
async def health_check() -> HealthResponse:
    """
    Health endpoint.

    Returns 200 with component-level status.
    Each component is 'ok' or 'error'.
    Overall status is 'healthy' only if all components are ok.
    """
    pg_status = await _check_postgres()
    redis_status = await _check_redis()

    overall = "healthy" if pg_status == "ok" and redis_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        postgres=pg_status,
        redis=redis_status,
    )


async def _check_postgres() -> str:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


async def _check_redis() -> str:
    try:
        redis = await get_redis()
        if await redis.ping():
            return "ok"
        return "error"
    except Exception:
        return "error"
