"""
AADAP — Tracing Tests
=======================
Tests for Phase 7 distributed tracing module.

Validates:
- TracingContext captures correlation ID from context
- Span timing and lifecycle
- Header injection for outgoing calls
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from aadap.core.tracing import Span, TracingContext, create_span


# ── TracingContext Tests ────────────────────────────────────────────────


def test_tracing_context_from_context_var():
    """TracingContext.current() reads from the correlation_id_ctx."""
    with patch(
        "aadap.core.tracing.correlation_id_ctx"
    ) as mock_ctx:
        mock_ctx.get.return_value = "test-correlation-123"
        ctx = TracingContext.current()

    assert ctx.correlation_id == "test-correlation-123"


def test_tracing_context_without_correlation_id():
    """TracingContext.current() returns None when no correlation ID is set."""
    with patch(
        "aadap.core.tracing.correlation_id_ctx"
    ) as mock_ctx:
        mock_ctx.get.return_value = None
        ctx = TracingContext.current()

    assert ctx.correlation_id is None


# ── Header Injection Tests ─────────────────────────────────────────────


def test_inject_headers_with_correlation_id():
    """inject_headers adds X-Correlation-ID when present."""
    ctx = TracingContext(correlation_id="abc-123")
    headers = ctx.inject_headers({})

    assert headers["X-Correlation-ID"] == "abc-123"
    assert "X-Trace-Timestamp" in headers


def test_inject_headers_without_correlation_id():
    """inject_headers omits X-Correlation-ID when None."""
    ctx = TracingContext(correlation_id=None)
    headers = ctx.inject_headers({})

    assert "X-Correlation-ID" not in headers
    assert "X-Trace-Timestamp" in headers


def test_inject_headers_preserves_existing():
    """inject_headers does not overwrite existing headers."""
    ctx = TracingContext(correlation_id="abc-123")
    headers = ctx.inject_headers({"Authorization": "Bearer token"})

    assert headers["Authorization"] == "Bearer token"
    assert headers["X-Correlation-ID"] == "abc-123"


# ── Span Tests ─────────────────────────────────────────────────────────


def test_span_creation():
    """Span is created with name and auto-generated ID."""
    span = Span(name="test.operation")
    assert span.name == "test.operation"
    assert len(span.span_id) == 16
    assert span.end_time is None
    assert span.duration_ms is None


def test_span_close():
    """Closing a span records end time and computes duration."""
    span = Span(name="test.operation")
    time.sleep(0.01)  # Small delay for measurable duration
    span.close()

    assert span.end_time is not None
    assert span.duration_ms is not None
    assert span.duration_ms > 0


def test_span_close_idempotent():
    """Closing a span twice does not change end_time."""
    span = Span(name="test.operation")
    span.close()
    first_end = span.end_time
    span.close()
    assert span.end_time == first_end


# ── create_span Context Manager ────────────────────────────────────────


def test_create_span_context_manager():
    """create_span auto-closes the span on exit."""
    with create_span("test.op") as span:
        assert span.name == "test.op"
        assert span.end_time is None

    assert span.end_time is not None
    assert span.duration_ms is not None


def test_create_span_with_metadata():
    """create_span passes metadata to the Span."""
    with create_span("test.op", job_id="abc", attempt=1) as span:
        pass

    assert span.metadata["job_id"] == "abc"
    assert span.metadata["attempt"] == 1


def test_create_span_on_exception():
    """Span is closed even if the block raises an exception."""
    with pytest.raises(ValueError):
        with create_span("test.failing") as span:
            raise ValueError("Test error")

    assert span.end_time is not None
    assert span.duration_ms is not None
