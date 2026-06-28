"""Clock and id-generator infrastructure adapters."""

from __future__ import annotations

import uuid_extensions

from lens_common.ports import SystemClock, UuidV7Generator

__all__ = [
    "PostgresClock",
    "SystemClock",
    "UuidV7Generator",
    "postgres_uuid7",
]


class PostgresClock(SystemClock):
    """Production clock that always returns a UTC-aware timestamp."""


def postgres_uuid7() -> uuid_extensions.UUID:  # pyright: ignore[reportAttributeAccessIssue]
    """Generate a UUIDv7 for use as a primary key in Postgres."""
    return uuid_extensions.uuid7()
