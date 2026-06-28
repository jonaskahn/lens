from __future__ import annotations

import contextlib
from typing import Any

from lens_application.ports import IdempotencyPort

__all__ = [
    "InMemoryIdempotencyStore",
    "RedisIdempotencyStore",
]


class InMemoryIdempotencyStore(IdempotencyPort):
    def __init__(self) -> None:
        self._keys: dict[str, bool] = {}

    async def mark_seen(self, key: str, *, ttl_seconds: int = 86400) -> bool:
        if key in self._keys:
            return False
        self._keys[key] = True
        return True

    async def is_seen(self, key: str) -> bool:
        return key in self._keys


class RedisIdempotencyStore(IdempotencyPort):
    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def mark_seen(self, key: str, *, ttl_seconds: int = 86400) -> bool:
        with contextlib.suppress(Exception):
            return bool(await self._redis.set(f"lens:idempotent:{key}", "1", nx=True, ex=ttl_seconds))
        return False

    async def is_seen(self, key: str) -> bool:
        try:
            return bool(await self._redis.exists(f"lens:idempotent:{key}"))
        except Exception:
            return False
