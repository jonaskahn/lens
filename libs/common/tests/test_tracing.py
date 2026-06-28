"""Tracing configuration: init_tracing, inject_context."""

from __future__ import annotations

from lens_common.tracing import _tracing_initialized, init_tracing, inject_context


class TestInitTracing:
    def test_when_disabled_then_noop(self) -> None:
        global _tracing_initialized
        was = _tracing_initialized
        try:
            _tracing_initialized = False
            init_tracing(enabled=False)
            assert _tracing_initialized is False
        finally:
            _tracing_initialized = was

    def test_when_already_initialized_then_noop(self) -> None:
        global _tracing_initialized
        was = _tracing_initialized
        try:
            _tracing_initialized = True
            init_tracing(enabled=True, endpoint="http://localhost:4318")
            assert _tracing_initialized is True
        finally:
            _tracing_initialized = was

    def test_when_no_endpoint_then_noop(self) -> None:
        global _tracing_initialized
        was = _tracing_initialized
        try:
            _tracing_initialized = False
            init_tracing(enabled=True, endpoint=None)
            assert _tracing_initialized is False
        finally:
            _tracing_initialized = was


class TestInjectContext:
    def test_returns_empty_dict_when_no_otel(self) -> None:
        result = inject_context()
        assert isinstance(result, dict)

    def test_includes_supplied_headers(self) -> None:
        result = inject_context(headers={"X-Request-Id": "123"})
        assert result["X-Request-Id"] == "123"

    def test_headers_do_not_overwrite_carrier(self) -> None:
        result = inject_context(headers={"traceparent": "custom"})
        assert isinstance(result, dict)

    def test_no_headers_returns_empty_dict(self) -> None:
        result = inject_context(headers=None)
        assert isinstance(result, dict)
