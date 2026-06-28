"""Errors: hierarchy, codes, payload formatting."""

from __future__ import annotations

import pytest

from lens_common.errors import (
    AppBaseError,
    ApplicationError,
    DomainError,
    ErrorCode,
    InfrastructureError,
)


def test_given_domain_error_when_raised_then_is_application_layer_error() -> None:
    with pytest.raises(DomainError) as exc_info:
        raise DomainError("bad input", details={"field": "host"})

    assert exc_info.value.code == ErrorCode.VALIDATION
    assert exc_info.value.http_status == 422
    assert exc_info.value.message == "bad input"
    assert exc_info.value.details == {"field": "host"}


def test_given_application_error_when_raised_then_is_subtype_of_base() -> None:
    err = ApplicationError("conflict", internal="traceback...")
    assert isinstance(err, AppBaseError)
    assert err.internal == "traceback..."


def test_given_error_when_to_payload_then_internal_excluded() -> None:
    err = InfrastructureError("db down", internal="connection refused", details={"db": "pg"})

    payload = err.to_payload()

    assert payload == {
        "code": ErrorCode.INTERNAL,
        "message": "db down",
        "details": {"db": "pg"},
    }
    assert "internal" not in payload


def test_given_roots_when_subclassed_then_codes_default() -> None:
    class ConflictError(ApplicationError):
        code = ErrorCode.CONFLICT
        http_status = 409

    err = ConflictError("duplicate")
    assert err.code == "conflict"
    assert err.http_status == 409
    assert err.to_payload()["code"] == "conflict"
