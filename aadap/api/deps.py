"""
AADAP — API Dependencies
==========================
Shared FastAPI dependency injectors for the API layer.

Architecture layer: L6 (Presentation).
All route handlers use these to access infrastructure without
coupling to implementation details.
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from aadap.core.middleware import correlation_id_ctx
from aadap.db.session import get_db_session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async DB session for request-scoped use.

    Commits on clean exit, rolls back on exception
    (delegated to ``get_db_session`` context manager).
    """
    async with get_db_session() as session:
        yield session


def get_correlation_id() -> str | None:
    """
    Return the correlation ID for the current request.

    Populated by ``CorrelationMiddleware`` on every request.
    """
    return correlation_id_ctx.get(None)


def get_current_user() -> str:
    """
    Return the identity of the current user.

    Stub: returns ``"system"`` until auth is implemented.
    Extensible — swap for JWT/OAuth extraction in production.
    """
    return "system"
