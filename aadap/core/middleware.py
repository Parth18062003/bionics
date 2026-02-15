"""
AADAP — Correlation ID Middleware
==================================
Injects and propagates a UUID-v4 correlation ID on every HTTP request.

Enforces: INV-06 (audit trail) and Phase 7 tracing interface.

The correlation ID is:
1. Read from the incoming ``X-Correlation-ID`` header (if present), OR
2. Generated as a new UUID v4.
3. Stored in a context variable accessible to all logging processors.
4. Returned in the response ``X-Correlation-ID`` header.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from aadap.core.config import get_settings

# ── Context Variable ────────────────────────────────────────────────────
# Accessible from anywhere in the same async context (logging, DB, etc.)
correlation_id_ctx: ContextVar[str | None] = ContextVar(
    "correlation_id", default=None
)


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every request carries a correlation ID.

    Format: UUID v4 (lowercase, hyphenated).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        settings = get_settings()
        header_name = settings.correlation_id_header

        # Accept from client or generate fresh
        incoming_id = request.headers.get(header_name)
        cid = incoming_id if incoming_id else str(uuid.uuid4())

        # Store in context var for logging / downstream use
        token = correlation_id_ctx.set(cid)
        try:
            response = await call_next(request)
            response.headers[header_name] = cid
            return response
        finally:
            correlation_id_ctx.reset(token)
