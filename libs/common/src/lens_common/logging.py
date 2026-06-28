"""Logging configuration: structlog with correlation-id context.

Logging is structured JSON by default (production) or key-value (development).
The :func:`configure_logging` entrypoint is idempotent so it can be called from
each app's startup without double-binding handlers.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Final

import structlog

__all__ = [
    "bind_context",
    "clear_context",
    "configure_logging",
    "correlation_id",
    "get_logger",
    "new_correlation_id",
]


_LEVEL_NAMES: Final[frozenset[str]] = frozenset(
    {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
)

_configured: bool = False

_correlation_id: ContextVar[str | None] = ContextVar("lens_correlation_id", default=None)


def correlation_id() -> str | None:
    """Return the current correlation id, if any."""
    return _correlation_id.get()


def new_correlation_id() -> str:
    """Generate a fresh correlation id and bind it to the current context."""
    import uuid_extensions

    cid = str(uuid_extensions.uuid7())
    _correlation_id.set(cid)
    return cid


def bind_context(**values: object) -> None:
    """Bind values to the structlog context for the current task/thread."""
    if "correlation_id" in values and values["correlation_id"] is not None:
        _correlation_id.set(str(values["correlation_id"]))
    structlog.contextvars.bind_contextvars(**values)


def clear_context() -> None:
    """Clear the current structlog and correlation-id context."""
    structlog.contextvars.clear_contextvars()
    _correlation_id.set(None)


@contextmanager
def bound_context(**values: object) -> Iterator[None]:
    """Context manager that binds ``values`` for the duration of the block."""
    tokens: list[object] = []
    try:
        for key, value in values.items():
            tokens.append(structlog.contextvars.bind_contextvars(**{key: value}))
        yield
    finally:
        for token in reversed(tokens):
            structlog.contextvars.unbind_contextvars(token)  # type: ignore[arg-type]


def _add_correlation_id(_logger: object, _method_name: str, event_dict: dict[str, object]) -> dict[str, object]:
    cid = _correlation_id.get()
    if cid is not None and "correlation_id" not in event_dict:
        event_dict["correlation_id"] = cid
    return event_dict


def configure_logging(
    level: str = "INFO",
    *,
    fmt: str = "json",
    force: bool = False,
) -> None:
    """Configure structlog + stdlib logging exactly once.

    Parameters:
        level: Standard level name (``DEBUG``/``INFO``/``WARNING``/``ERROR``).
        fmt: ``"json"`` for production, ``"console"`` for local development.
        force: Reconfigure even if already configured (used in tests).
    """
    global _configured
    if _configured and not force:
        return

    normalized_level = level.upper()
    if normalized_level not in _LEVEL_NAMES:
        raise ValueError(f"invalid log level: {level!r}")

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, normalized_level),
        force=force,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        _add_correlation_id,  # type: ignore[list-item]
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.types.Processor
    if fmt == "json":
        renderer = structlog.processors.JSONRenderer()
    elif fmt == "console":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        raise ValueError(f"invalid log format: {fmt!r}")

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, normalized_level),
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> Any:
    """Return a configured structlog logger.

    The returned logger binds any per-call context via ``log.bind(**kwargs)``.
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()
