"""Application-layer exceptions: not-found, conflict, validation.

These wrap domain errors so the transport layer can map them to HTTP status
codes uniformly without knowing the domain layer's hierarchy.
"""

from __future__ import annotations

from lens_common.errors import ApplicationError, ErrorCode

__all__ = [
    "ApplicationError",
    "ConflictError",
    "NotFoundError",
    "ValidationFailed",
]


class NotFoundError(ApplicationError):
    """Requested entity does not exist."""

    code = ErrorCode.NOT_FOUND
    http_status = 404


class ConflictError(ApplicationError):
    """Persistence-layer uniqueness violation or policy conflict."""

    code = ErrorCode.CONFLICT
    http_status = 409


class ValidationFailed(ApplicationError):
    """Input fails business validation (e.g. interval below floor)."""

    code = ErrorCode.VALIDATION
    http_status = 422
