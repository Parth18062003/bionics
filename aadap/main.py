"""
AADAP — FastAPI Application
=============================
Application factory with lifecycle management and middleware pipeline.

Architecture layer: L6 (Presentation) — FastAPI skeleton.
All middleware is pluggable (Risk R4 mitigation).

Usage:
    uvicorn aadap.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from aadap.api.health import router as health_router
from aadap.core.config import get_settings
from aadap.core.logging import configure_logging, get_logger
from aadap.core.middleware import CorrelationMiddleware
from aadap.core.redis import close_redis, init_redis
from aadap.db.session import close_db, init_db


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifecycle.

    Startup: configure logging, connect DB & Redis.
    Shutdown: close DB & Redis connections.
    """
    logger = get_logger("aadap.main")

    # ── Startup ──────────────────────────────────────────────────────
    configure_logging()
    logger.info("app.starting", environment=get_settings().environment.value)

    await init_db()
    logger.info("db.connected")

    await init_redis()
    logger.info("redis.connected")

    logger.info("app.started")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("app.stopping")
    await close_redis()
    await close_db()
    logger.info("app.stopped")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    application = FastAPI(
        title="AADAP",
        description="Autonomous AI Developer Agents Platform",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    # ── Middleware (pluggable chain — Risk R4) ────────────────────────
    application.add_middleware(CorrelationMiddleware)

    # ── Routers ──────────────────────────────────────────────────────
    application.include_router(health_router)

    return application


# Module-level instance for ``uvicorn aadap.main:app``
app = create_app()
