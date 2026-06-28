"""Clock and id-generator infrastructure adapters."""

from __future__ import annotations

from lens_infrastructure.clock import PostgresClock, postgres_uuid7


def test_given_clock_when_now_then_is_utc_aware() -> None:
    clock = PostgresClock()
    now = clock.now()
    assert now.tzinfo is not None
    assert now.utcoffset() is not None


def test_given_uuid7_when_generated_then_is_version_7() -> None:
    value = postgres_uuid7()
    assert value.version == 7
