"""Rate limiter: in-memory sliding-window for tests + pluggable backends.

The middleware key is the resolved API-key id when auth has populated
``request.state.api_key_id``; otherwise it falls back to the immediate
client peer (never ``X-Forwarded-For``). Per-instance state is
intentionally simple so the in-memory backend works for tests; the
composition root wires a Redis-backed limiter for production.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

__all__ = [
    "InMemoryRateLimiter",
    "RateLimitMiddleware",
    "RateLimiter",
    "resolve_rate_limit_key",
]


class RateLimiter:
    async def is_allowed(self, key: str, *, max_requests: int, window_seconds: int) -> bool:
        raise NotImplementedError

    async def reset(self, key: str) -> None:
        raise NotImplementedError


class InMemoryRateLimiter(RateLimiter):
    def __init__(self) -> None:
        self._windows: dict[str, list[float]] = {}

    async def is_allowed(self, key: str, *, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        window = self._windows.setdefault(key, [])
        window = [ts for ts in window if now - ts < window_seconds]
        self._windows[key] = window
        if len(window) >= max_requests:
            return False
        window.append(now)
        return True

    async def reset(self, key: str) -> None:
        self._windows.pop(key, None)


def resolve_rate_limit_key(request: Request) -> str:
    """Return the rate-limit bucket key for a request.

    The selector prefers the resolved API-key id (set by auth) and only
    falls back to the immediate peer (``request.client.host``). The
    ``X-Forwarded-For`` header is deliberately **ignored**: a trusted
    proxy must rewrite the client peer at the edge; honoring the header
    unconditionally lets a single attacker rotate their identity and
    bypass the limiter.
    """
    api_key_id: str | None = getattr(request.state, "api_key_id", None)
    if api_key_id:
        return f"rate:key:{api_key_id}"
    client_host = request.client.host if request.client else "unknown"
    return f"rate:ip:{client_host}"


class RateLimitMiddleware:
    """Pure ASGI rate-limit middleware.

    Implemented without :class:`starlette.middleware.base.BaseHTTPMiddleware`
    so it does not break streaming responses and so the typed
    ``app: ASGIApp`` signature lines up with Starlette's middleware
    factory protocol.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        limiter: RateLimiter,
        max_requests: int = 100,
        window_seconds: int = 60,
        key_selector: Callable[[Request], str] | None = None,
    ) -> None:
        self._app = app
        self._limiter = limiter
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._key_selector = key_selector or resolve_rate_limit_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        request = Request(scope)
        key = self._key_selector(request)
        allowed = await self._limiter.is_allowed(
            key,
            max_requests=self._max_requests,
            window_seconds=self._window_seconds,
        )
        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests",
                    "retry_after": self._window_seconds,
                },
                headers={"Retry-After": str(self._window_seconds)},
            )
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)
