from __future__ import annotations

import random
from collections.abc import AsyncIterator
from typing import Final

__all__ = [
    "async_backoff",
    "backoff_sleep_seconds",
]

_JITTER_FACTOR: Final[float] = 0.1
_DEFAULT_MAX_SECONDS: Final[float] = 300.0


def backoff_sleep_seconds(
    attempt: int,
    *,
    base: float = 1.0,
    cap: float = _DEFAULT_MAX_SECONDS,
) -> float:
    delay: float = base * (2 ** (attempt - 1))
    if delay > cap:
        delay = cap
    jitter: float = delay * _JITTER_FACTOR * random.random()
    return delay + jitter


async def async_backoff(
    max_attempts: int = 5,
    *,
    base: float = 1.0,
    cap: float = _DEFAULT_MAX_SECONDS,
) -> AsyncIterator[int]:
    import asyncio

    for attempt in range(1, max_attempts + 1):
        yield attempt
        if attempt < max_attempts:
            await asyncio.sleep(backoff_sleep_seconds(attempt, base=base, cap=cap))
