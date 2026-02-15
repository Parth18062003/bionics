"""
AADAP — Structured Logging
============================
JSON-structured logging with automatic correlation ID injection.

Enforces: INV-06 (Complete audit trail for all actions and decisions).

Usage:
    from aadap.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("task.created", task_id="abc-123")
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from aadap.core.config import get_settings


def _add_app_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add application-level context to every log entry."""
    settings = get_settings()
    event_dict.setdefault("app", settings.app_name)
    event_dict.setdefault("environment", settings.environment.value)
    return event_dict


def _add_correlation_id(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Inject correlation_id from context variable if not already present.

    The correlation ID is set by the CorrelationMiddleware on each request.
    """
    from aadap.core.middleware import correlation_id_ctx

    cid = correlation_id_ctx.get(None)
    if cid is not None:
        event_dict.setdefault("correlation_id", cid)
    return event_dict


def configure_logging() -> None:
    """
    Configure structlog + stdlib logging.

    Must be called once at application startup (before any log emission).
    """
    settings = get_settings()

    # Choose renderer based on config
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _add_app_context,
        _add_correlation_id,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.db_echo_sql else logging.WARNING
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger bound to the given module name."""
    return structlog.get_logger(name)
