"""Distributed lock adapters.

An in-process lock is shipped for unit tests and a Redis lock
implementation that production deployments can opt into. The Redis
variant uses ``SET NX PX`` with a unique token and a safe ``DEL`` via a
Lua check-and-delete script.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Protocol

from lens_application.pipeline import LockPort

__all__ = [
    "InMemoryLockAdapter",
    "RedisLockAdapter",
]


class InMemoryLockAdapter(LockPort):
    """An in-process :class:`LockPort` useful for tests and single-node setups."""

    def __init__(self) -> None:
        self._held: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, *, ttl_seconds: int, token: str) -> str:
        async with self._lock:
            if key in self._held:
                return ""
            self._held[key] = token
            return token

    async def release(self, key: str, token: str) -> None:
        async with self._lock:
            if self._held.get(key) == token:
                del self._held[key]

    async def renew(self, key: str, token: str, *, ttl_seconds: int) -> bool:
        async with self._lock:
            return self._held.get(key) == token


class _RedisLike(Protocol):
    async def set(self, name: str, value: str, *, nx: bool, px: int) -> str | None: ...

    async def eval(self, script: str, numkeys: int, *args: str) -> Any: ...


_RELEASE_LUA = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


class RedisLockAdapter(LockPort):
    """A Redis-backed :class:`LockPort` with safe release semantics."""

    def __init__(self, redis: _RedisLike) -> None:
        self._redis = redis

    async def acquire(self, key: str, *, ttl_seconds: int, token: str | None = None) -> str:
        value = token or uuid.uuid4().hex
        result = await self._redis.set(
            key,
            value,
            nx=True,
            px=ttl_seconds * 1000,
        )
        return value if result else ""

    async def release(self, key: str, token: str) -> None:
        await self._redis.eval(_RELEASE_LUA, 1, key, token)

    async def renew(self, key: str, token: str, *, ttl_seconds: int) -> bool:
        from redis.asyncio.client import Redis as _RealRedis

        if isinstance(self._redis, _RealRedis):
            from redis.asyncio.lock import Lock

            return await Lock(self._redis, key, timeout=ttl_seconds).reacquire()
        # Fallback: treat renew as a no-op for unknown backends.
        return False
