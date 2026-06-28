"""API-key admin use cases.

These use cases back ``POST /admin/api-keys``, ``GET /admin/api-keys``,
and ``DELETE /admin/api-keys/{id}`` (the operations that mint, list,
and revoke bearer tokens for the public REST API). The plaintext key
is returned **once** at create time; only the SHA-256 hash is stored.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lens_application.ports import ApiKeyRepository, UnitOfWork
from lens_application.use_cases._base import UseCase

__all__ = [
    "ApiKeyCreateResult",
    "CreateApiKeyUseCase",
    "DeleteApiKeyUseCase",
    "ListApiKeysUseCase",
]


@dataclass(slots=True)
class ApiKeyCreateResult:
    """One minted API key.

    ``id`` is the public key id; ``plaintext`` is the bearer token the
    caller must store immediately - it is never returned again.
    """

    id: str
    name: str
    plaintext: str
    scopes: list[str]
    enabled: bool = True


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _mint_key() -> str:
    """Return a fresh bearer token (URL-safe, 32 bytes of entropy)."""
    return secrets.token_urlsafe(32)


class CreateApiKeyUseCase(UseCase[dict[str, Any], ApiKeyCreateResult]):
    """Mint a new API key and return its plaintext exactly once."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        api_key_repo: ApiKeyRepository,
    ) -> None:
        super().__init__(uow_factory)
        self._repo = api_key_repo

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> ApiKeyCreateResult:
        name = params["name"]
        scopes: list[str] = list(params.get("scopes", ["read"]))
        enabled = bool(params.get("enabled", True))
        plaintext = _mint_key()
        key_hash = _hash_key(plaintext)
        record = await self._repo.create(
            name=name,
            key_hash=key_hash,
            scopes=scopes,
            enabled=enabled,
        )
        return ApiKeyCreateResult(
            id=str(record["id"]),
            name=record["name"],
            plaintext=plaintext,
            scopes=list(record.get("scopes", scopes)),
            enabled=bool(record.get("enabled", enabled)),
        )


class ListApiKeysUseCase(UseCase[dict[str, Any], list[dict[str, Any]]]):
    """List API keys (admin UI)."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        api_key_repo: ApiKeyRepository,
    ) -> None:
        super().__init__(uow_factory)
        self._repo = api_key_repo

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> list[dict[str, Any]]:
        limit: int = int(params.get("limit", 100))
        return await self._repo.list(limit=limit)


class DeleteApiKeyUseCase(UseCase[str, None]):
    """Revoke one API key."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        api_key_repo: ApiKeyRepository,
    ) -> None:
        super().__init__(uow_factory)
        self._repo = api_key_repo

    async def run(self, key_id: str, uow: UnitOfWork) -> None:
        await self._repo.delete(key_id)
