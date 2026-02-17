"""
AADAP — Distributed Tracing
==============================
End-to-end correlation ID propagation and span management.

Architecture layer: L6 / cross-cutting.
Phase 7 contract: "Correlation ID propagated end-to-end."

Builds on the existing ``CorrelationMiddleware`` and ``correlation_id_ctx``
context variable.  Adds span-level timing and header injection for
outgoing HTTP calls (e.g. to Databricks).

Usage:
    from aadap.core.tracing import TracingContext, create_span

    ctx = TracingContext.current()
    with create_span("databricks.submit") as span:
        headers = ctx.inject_headers({})
        # pass headers to outgoing HTTP call
    print(span.duration_ms)
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generator

from aadap.core.middleware import correlation_id_ctx


@dataclass
class Span:
    """A single timed span within a trace."""

    name: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    start_time: float = field(default_factory=time.monotonic)
    end_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float | None:
        """Duration in milliseconds, or None if still open."""
        if self.end_time is None:
            return None
        return round((self.end_time - self.start_time) * 1000, 2)

    def close(self) -> None:
        """Close the span, recording end time."""
        if self.end_time is None:
            self.end_time = time.monotonic()


@dataclass
class TracingContext:
    """
    Holds correlation ID and span tree for the current request.

    The correlation ID is sourced from the ``correlation_id_ctx``
    context variable set by ``CorrelationMiddleware``.
    """

    correlation_id: str | None = None
    spans: list[Span] = field(default_factory=list)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def current(cls) -> TracingContext:
        """Create a TracingContext from the current request context."""
        return cls(correlation_id=correlation_id_ctx.get(None))

    def inject_headers(
        self, headers: dict[str, str]
    ) -> dict[str, str]:
        """
        Inject tracing headers into an outgoing HTTP request.

        Adds ``X-Correlation-ID`` and ``X-Trace-Timestamp`` so
        downstream services can correlate logs.
        """
        if self.correlation_id:
            headers["X-Correlation-ID"] = self.correlation_id
        headers["X-Trace-Timestamp"] = datetime.now(timezone.utc).isoformat()
        return headers


@contextmanager
def create_span(name: str, **metadata: Any) -> Generator[Span, None, None]:
    """
    Context manager that creates and auto-closes a timed span.

    Usage:
        with create_span("databricks.submit", job_id="abc") as span:
            ...
        print(span.duration_ms)
    """
    span = Span(name=name, metadata=metadata)
    try:
        yield span
    finally:
        span.close()
