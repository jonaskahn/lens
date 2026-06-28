"""API-key auth dependency.

The auth layer accepts any non-empty ``Authorization: Bearer <key>`` and looks up
the SHA-256 hash against the ``api_keys`` table. Scope checks map the key's
stored scopes (``read``/``write``/``admin``) to per-endpoint requirements.

The :func:`resolve_api_key` dependency also writes the resolved key id to
``request.state.api_key_id`` so the rate limiter can bucket requests
per-key (see :mod:`lens_api.rate_limit`).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request

__all__ = ["ApiKey", "Scope", "require_scope", "resolve_api_key"]


class Scope:
    """Scope strings used in the ``api_keys`` table."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class ApiKey:
    """A successfully-resolved API key."""

    id: str
    name: str
    scopes: tuple[str, ...]


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing API key")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="invalid authorization header")
    return parts[1].strip()


def resolve_api_key(request: Request) -> ApiKey:
    """FastAPI dependency: return the resolved :class:`ApiKey` or raise 401/403."""
    auth_header: str | None = request.headers.get("authorization")
    raw = _extract_bearer(auth_header)
    key_hash = _hash_key(raw)
    lookup = getattr(request.app.state, "api_key_lookup", None)
    if lookup is None:
        raise HTTPException(status_code=401, detail="api key lookup not configured")
    result = lookup(key_hash)
    if result is None:
        raise HTTPException(status_code=401, detail="invalid API key")
    if not result.get("enabled", True):
        raise HTTPException(status_code=403, detail="api key disabled")
    key_id = str(result["id"])
    request.state.api_key_id = key_id
    return ApiKey(
        id=key_id,
        name=result["name"],
        scopes=tuple(result.get("scopes", ())),
    )


def require_scope(*required: str) -> Any:
    """Build a FastAPI dependency that checks for any of the given scopes.

    Scopes are not hierarchical: a key with ``admin`` only does **not**
    imply ``write`` or ``read``. Operators must grant each scope
    explicitly.
    """

    def _check(api_key: ApiKey = Depends(resolve_api_key)) -> ApiKey:
        if not any(s in api_key.scopes for s in required):
            raise HTTPException(
                status_code=403,
                detail=f"missing required scope: {'|'.join(required)}",
            )
        return api_key

    return _check
