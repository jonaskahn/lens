"""Exception handlers: map domain/application errors to HTTP responses."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from lens_common.errors import AppBaseError, ErrorCode

__all__ = ["register_exception_handlers", "unhandled_exception_logger"]


def _payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return {"error": body}


def register_exception_handlers(app: FastAPI) -> None:
    """Register handlers for :class:`AppBaseError` and unhandled exceptions."""

    @app.exception_handler(AppBaseError)
    async def _app_error_handler(_request: Request, exc: AppBaseError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=_payload(exc.code, exc.message, exc.details))

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            400: ErrorCode.VALIDATION,
            401: ErrorCode.UNAUTHORIZED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            409: ErrorCode.CONFLICT,
            422: ErrorCode.VALIDATION,
            429: ErrorCode.RATE_LIMITED,
        }.get(exc.status_code, ErrorCode.INTERNAL)
        details: dict[str, Any] | None = None
        if isinstance(exc.detail, dict):
            if "code" in exc.detail and isinstance(exc.detail["code"], str):  # pyright: ignore[reportArgumentType]
                code = exc.detail["code"]  # pyright: ignore[reportArgumentType]
            message = str(exc.detail.get("message", "http error"))
            inner = exc.detail.get("details")
            if isinstance(inner, dict):
                details = inner
            else:
                extras = {k: v for k, v in exc.detail.items() if k not in {"code", "message", "details"}}
                if extras:
                    details = extras
        elif isinstance(exc.detail, str):
            message = exc.detail
        else:
            message = "http error"
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(code, message, details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_payload(
                ErrorCode.VALIDATION,
                "validation error",
                {"errors": exc.errors()},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        unhandled_exception_logger(request, exc)
        return JSONResponse(
            status_code=500,
            content=_payload(ErrorCode.INTERNAL, "internal server error"),
        )


_logger = logging.getLogger("lens_api.unhandled")


def unhandled_exception_logger(request: Request, exc: Exception) -> None:
    """Log unhandled exceptions with the request path/method for tracing."""
    _logger.exception(
        "unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
