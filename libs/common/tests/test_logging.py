"""Logging: JSON output, correlation id propagation, idempotent setup."""

from __future__ import annotations

import io
import json
import logging
from contextlib import redirect_stdout

from lens_common.logging import (
    bind_context,
    clear_context,
    configure_logging,
    correlation_id,
    get_logger,
    new_correlation_id,
)


def _capture_log(level: str, fmt: str) -> tuple[io.StringIO, logging.LogRecord]:
    configure_logging(level=level, fmt=fmt, force=True)
    buffer = io.StringIO()
    logger = get_logger("test")
    with redirect_stdout(buffer):
        logger.info("hello", key="value")
    return buffer, None  # type: ignore[return-value]


def test_given_json_format_when_logging_then_output_is_json() -> None:
    buffer, _ = _capture_log("INFO", "json")
    payload = json.loads(buffer.getvalue().splitlines()[-1])
    assert payload["event"] == "hello"
    assert payload["key"] == "value"
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_given_correlation_id_bound_when_logging_then_emitted_in_event() -> None:
    configure_logging(level="INFO", fmt="json", force=True)
    cid = new_correlation_id()
    bind_context(correlation_id=cid)

    buffer = io.StringIO()
    logger = get_logger("test")
    with redirect_stdout(buffer):
        logger.info("hello")

    payload = json.loads(buffer.getvalue().splitlines()[-1])
    assert payload["correlation_id"] == cid
    assert correlation_id() == cid

    clear_context()
    assert correlation_id() is None


def test_given_configure_logging_called_twice_then_only_one_handler() -> None:
    configure_logging(level="INFO", fmt="json", force=True)
    handlers_after_first = len(logging.getLogger().handlers)
    configure_logging(level="INFO", fmt="json", force=False)
    assert len(logging.getLogger().handlers) == handlers_after_first


def test_given_console_format_when_logging_then_output_is_key_value() -> None:
    buffer, _ = _capture_log("INFO", "console")
    line = buffer.getvalue().strip().splitlines()[-1]
    assert "hello" in line
    import re

    assert re.search(r"key", line) is not None
    assert re.search(r"value", line) is not None
