from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = [
    "init_tracing",
    "inject_context",
]

_tracing_initialized: bool = False


def init_tracing(
    *,
    service_name: str = "lens",
    endpoint: str | None = None,
    enabled: bool = True,
) -> None:
    global _tracing_initialized
    if _tracing_initialized or not enabled:
        return
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore[import-not-found]
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore[import-not-found]

        if endpoint is None:
            return
        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracing_initialized = True
    except ImportError:
        pass


def inject_context(headers: Mapping[str, Any] | None = None) -> dict[str, str]:
    carrier: dict[str, str] = {}
    try:
        from opentelemetry import propagate  # pyright: ignore[reportMissingImports]
        from opentelemetry.trace import get_current_span  # type: ignore[import-not-found]

        current = get_current_span()
        if current.is_recording():
            propagate.inject(carrier)
    except Exception:
        pass
    if headers:
        for key, value in headers.items():
            if key not in carrier:
                carrier[key] = str(value)
    return carrier
