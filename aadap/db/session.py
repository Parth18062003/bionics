"""
AADAP — Database Session Management
=====================================
Async SQLAlchemy session factory with connection pooling.

Usage:
    from aadap.db.session import get_db_session

    async with get_db_session() as session:
        result = await session.execute(...)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from aadap.core.config import get_settings

# ── Module-level state ──────────────────────────────────────────────────

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> AsyncEngine:
    """
    Create the async engine and session factory.

    Called once during application startup.
    """
    global _engine, _session_factory
    settings = get_settings()

    _engine = create_async_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_overflow,
        echo=settings.db_echo_sql,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    return _engine


async def close_db() -> None:
    """Dispose the engine and its connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional async session.

    Commits on clean exit, rolls back on exception.
    """
    if _session_factory is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() during startup."
        )
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_engine() -> AsyncEngine:
    """Return the current engine. Raises if not initialized."""
    if _engine is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() during startup."
        )
    return _engine
