"""Correlation-id middleware (pure ASGI).

Reads (or generates) an ``X-Correlation-Id`` header per request, binds it
to the structlog context so downstream use cases + worker logs share the
same trace id, echoes the header on the response, and emits one
structured access log line per request.

Implemented as a pure ASGI app (no :class:`BaseHTTPMiddleware`) so it
does not buffer the response body, which matters for the streaming
diff endpoint (``GET /changes/{id}/diff``).
"""

from __future__ import annotations

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lens_common.logging import (
    bind_context,
    clear_context,
    new_correlation_id,
)

__all__ = ["CorrelationIdMiddleware"]

_HEADER_LOWER = b"x-correlation-id"
_HEADER_UPPER = b"X-Correlation-Id"

_logger = logging.getLogger("lens_api.access")


class CorrelationIdMiddleware:
    """Pure ASGI middleware that binds a correlation id per request."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        headers = scope.get("headers") or []
        cid: str | None = None
        for name, value in headers:
            if name == _HEADER_LOWER:
                try:
                    cid = value.decode("latin-1")
                except Exception:
                    cid = None
                break
        if not cid:
            cid = new_correlation_id()

        method = scope.get("method", "")
        path = scope.get("path", "")
        bind_context(correlation_id=cid, method=method, path=path)
        start = time.monotonic()
        status_code = 500
        cid_value = cid.encode("latin-1")
        response_started = False

        async def _send(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers_list = list(message.get("headers") or [])
                headers_list = [(n, v) for n, v in headers_list if n != _HEADER_UPPER]
                headers_list.append((_HEADER_UPPER, cid_value))
                message = {**message, "headers": headers_list}
                response_started = True
            await send(message)

        try:
            await self._app(scope, receive, _send)
        except Exception:
            elapsed_ms = (time.monotonic() - start) * 1000.0
            _logger.exception(
                "request failed %s %s in %.1fms (cid=%s)",
                method,
                path,
                elapsed_ms,
                cid,
            )
            if not response_started:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (_HEADER_UPPER, cid_value),
                        ],
                    },
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"error":{"code":"internal","message":"internal server error"}}',
                        "more_body": False,
                    },
                )
            clear_context()
            raise
        elapsed_ms = (time.monotonic() - start) * 1000.0
        _logger.info(
            "%s %s -> %s in %.1fms (cid=%s)",
            method,
            path,
            status_code,
            elapsed_ms,
            cid,
        )
        clear_context()
