from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

from lens_application.ports import ThrottlePort

__all__ = [
    "InMemoryThrottle",
    "RedisThrottle",
]


class InMemoryThrottle(ThrottlePort):
    def __init__(self, *, max_rate: int = 10) -> None:
        self._buckets: dict[str, _TokenBucket] = {}
        self._max_rate = max_rate

    async def acquire(self, host: str) -> bool:
        if host not in self._buckets:
            self._buckets[host] = _TokenBucket(max_rate=self._max_rate)
        return self._buckets[host].acquire()

    async def release(self, host: str) -> None:
        pass

    async def delay_seconds(self, host: str) -> float:
        if host not in self._buckets:
            return 0.0
        return self._buckets[host].wait_seconds()


class _TokenBucket:
    def __init__(self, *, max_rate: int = 10) -> None:
        self._max_rate = max_rate
        self._interval = 1.0 / max_rate
        self._last_time = time.monotonic()
        self._tokens: float = max_rate
        self._lock = asyncio.Lock()

    def acquire(self) -> bool:
        now = time.monotonic()
        elapsed = now - self._last_time
        self._tokens = min(self._max_rate, self._tokens + elapsed * self._max_rate)
        self._last_time = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def wait_seconds(self) -> float:
        if self._tokens >= 1.0:
            return 0.0
        return (1.0 - self._tokens) * self._interval


class RedisThrottle(ThrottlePort):
    def __init__(self, redis: Any, *, max_rate: int = 10) -> None:
        self._redis = redis
        self._max_rate = max_rate
        self._interval = 1.0 / max_rate

    async def acquire(self, host: str) -> bool:
        now = time.time()
        key = f"lens:throttle:{host}"
        with contextlib.suppress(Exception):
            current = await self._redis.get(key)
            if current is None:
                await self._redis.set(key, str(now), px=int(self._interval * 1000))
                return True
        return False

    async def release(self, host: str) -> None:
        pass

    async def delay_seconds(self, host: str) -> float:
        key = f"lens:throttle:{host}"
        current = await self._redis.get(key)
        if current is None:
            return 0.0
        elapsed = time.time() - float(current)
        if elapsed >= self._interval:
            return 0.0
        return self._interval - elapsed
