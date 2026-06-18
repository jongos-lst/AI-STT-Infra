"""Structured logging: JSON in staging/prod, pretty in dev. Always includes trace_id."""
from __future__ import annotations

import logging
import sys

import structlog
from opentelemetry import trace

from app.core.config import settings


def _add_trace_context(_logger: object, _method: str, event_dict: dict[str, object]) -> dict[str, object]:
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    if ctx and ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def setup_logging() -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared: list[object] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        _add_trace_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if settings.is_dev:
        renderer: object = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.JSONRenderer()
    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=settings.log_level, format="%(message)s")


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
