"""lens common: shared kernel (config, logging, errors, ports, DI, types)."""

from __future__ import annotations

from lens_common.config import AppRole, LogFormat, Settings, load_settings
from lens_common.di import Container, Scope
from lens_common.errors import (
    AppBaseError,
    ApplicationError,
    DomainError,
    ErrorCode,
    InfrastructureError,
)
from lens_common.health import ComponentStatus, HealthCheck, HealthStatus
from lens_common.lifecycle import GracefulShutdown
from lens_common.logging import (
    bind_context,
    bound_context,
    clear_context,
    configure_logging,
    correlation_id,
    get_logger,
    new_correlation_id,
)
from lens_common.metrics import MetricFactory, Metrics, create_metrics, generate_latest_metrics
from lens_common.ports import ClockPort, IdGeneratorPort, SystemClock, UuidV7Generator
from lens_common.retry import async_backoff, backoff_sleep_seconds
from lens_common.tracing import init_tracing, inject_context
from lens_common.types import CorrelationId, Id, Page, PageRequest

__version__ = "0.1.0"

__all__ = [
    "AppBaseError",
    "AppRole",
    "ApplicationError",
    "ClockPort",
    "ComponentStatus",
    "Container",
    "CorrelationId",
    "DomainError",
    "ErrorCode",
    "GracefulShutdown",
    "HealthCheck",
    "HealthStatus",
    "Id",
    "IdGeneratorPort",
    "InfrastructureError",
    "LogFormat",
    "MetricFactory",
    "Metrics",
    "Page",
    "PageRequest",
    "Scope",
    "Settings",
    "SystemClock",
    "UuidV7Generator",
    "async_backoff",
    "backoff_sleep_seconds",
    "bind_context",
    "bound_context",
    "clear_context",
    "configure_logging",
    "correlation_id",
    "create_metrics",
    "generate_latest_metrics",
    "get_logger",
    "init_tracing",
    "inject_context",
    "load_settings",
    "new_correlation_id",
]
