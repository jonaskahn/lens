"""Retry / backoff utilities."""

from __future__ import annotations

from lens_common.retry import async_backoff, backoff_sleep_seconds


class TestBackoffSleepSeconds:
    def test_first_attempt_base_delay(self) -> None:
        delay = backoff_sleep_seconds(1, base=1.0)
        assert delay >= 1.0
        assert delay <= 1.0 + 1.0 * 0.1  # + jitter

    def test_exponential_growth(self) -> None:
        d1 = backoff_sleep_seconds(1, base=2.0)
        d2 = backoff_sleep_seconds(2, base=2.0)
        assert d2 > d1

    def test_cap_applied(self) -> None:
        delay = backoff_sleep_seconds(100, base=1.0, cap=5.0)
        assert delay <= 5.0 + 5.0 * 0.1

    def test_no_jitter_exceeds_max(self) -> None:
        delay = backoff_sleep_seconds(10, base=1.0, cap=10.0)
        assert delay <= 10.0 + 1.0


class TestAsyncBackoff:
    async def test_yields_attempt_numbers(self) -> None:
        attempts = [a async for a in async_backoff(max_attempts=3)]
        assert attempts == [1, 2, 3]

    async def test_single_attempt(self) -> None:
        attempts = [a async for a in async_backoff(max_attempts=1)]
        assert attempts == [1]

    async def test_custom_base_and_cap(self) -> None:
        attempts = [a async for a in async_backoff(max_attempts=2, base=0.5, cap=1.0)]
        assert attempts == [1, 2]
