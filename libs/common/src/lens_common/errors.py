"""Typed exception hierarchy shared across all lens layers.

The hierarchy is rooted in :class:`AppBaseError` and has three category roots that
map to the architectural layers (``DomainError`` -> ``application`` ->
``InfrastructureError``). Each leaf error carries a stable, machine-readable
``code`` plus a safe ``message`` for end-users and an optional ``internal``
detail for logs.
"""

from __future__ import annotations

from typing import Any, Final

__all__ = [
    "AppBaseError",
    "ApplicationError",
    "DomainError",
    "ErrorCode",
    "InfrastructureError",
]


class ErrorCode:
    """Stable, machine-readable error codes used by transport layers."""

    VALIDATION: Final[str] = "validation_error"
    NOT_FOUND: Final[str] = "not_found"
    CONFLICT: Final[str] = "conflict"
    UNAUTHORIZED: Final[str] = "unauthorized"
    FORBIDDEN: Final[str] = "forbidden"
    RATE_LIMITED: Final[str] = "rate_limited"
    INTERNAL: Final[str] = "internal"


class AppBaseError(Exception):
    """Root of the lens exception hierarchy.

    Carries an HTTP-style ``code`` for transport mapping, a user-safe ``message``,
    and an optional ``internal`` detail that must never be returned to clients.
    """

    code: str = ErrorCode.INTERNAL
    http_status: int = 500

    def __init__(
        self,
        message: str,
        *,
        internal: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.internal = internal
        self.details: dict[str, Any] = dict(details) if details else {}

    def to_payload(self) -> dict[str, Any]:
        """Build a transport-safe error body (excludes ``internal``)."""
        body: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return body


class DomainError(AppBaseError):
    """Invariant violations raised from the domain layer (libraries/domain)."""

    code = ErrorCode.VALIDATION
    http_status = 422


class ApplicationError(AppBaseError):
    """Use-case failures (not-found, conflict, validation) from the application layer."""

    code = ErrorCode.VALIDATION
    http_status = 422


class InfrastructureError(AppBaseError):
    """Adapter / infrastructure failures (DB, broker, crawler, storage)."""

    code = ErrorCode.INTERNAL
    http_status = 500
