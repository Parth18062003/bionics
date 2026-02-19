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
from aadap.api.routes import (
    approvals_router,
    artifacts_router,
    execution_router,
    marketplace_router,
    tasks_router,
)
from aadap.api.routes.explorer import router as explorer_router
from aadap.core.config import get_settings
from aadap.core.logging import configure_logging, get_logger
from aadap.core.middleware import CorrelationMiddleware
from aadap.core.memory_store import close_memory_store, init_memory_store
from aadap.db.session import close_db, init_db
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifecycle.

    Startup: configure logging, connect DB & in-memory store.
    Shutdown: close DB & in-memory store.
    """
    logger = get_logger("aadap.main")

    # ── Startup ──────────────────────────────────────────────────────
    configure_logging()
    logger.info("app.starting", environment=get_settings().environment.value)

    await init_db()
    logger.info("db.connected")

    await init_memory_store()
    logger.info("memory.initialized")

    logger.info("app.started")
    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("app.stopping")
    await close_memory_store()
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
    origins = ["http://localhost:3000", "http://172.28.96.1:3000"]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,  # Adjust in production,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # ── Routers ──────────────────────────────────────────────────────
    application.include_router(health_router)
    application.include_router(tasks_router)
    application.include_router(approvals_router)
    application.include_router(artifacts_router)
    application.include_router(marketplace_router)
    application.include_router(execution_router)
    application.include_router(explorer_router)

    return application


# Module-level instance for ``uvicorn aadap.main:app``
app = create_app()
