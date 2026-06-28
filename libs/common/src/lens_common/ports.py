"""Time and id generation ports (interfaces).

Concrete implementations live in ``lens_infrastructure``. Defining them in
``common`` keeps every layer able to depend on them without dragging I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import UUID

__all__ = [
    "ClockPort",
    "IdGeneratorPort",
    "SystemClock",
    "UuidV7Generator",
]


class ClockPort(Protocol):
    """Returns the current instant as a timezone-aware UTC datetime."""

    def now(self) -> datetime: ...


class IdGeneratorPort(Protocol):
    """Generates time-ordered UUIDv7 identifiers."""

    def new(self) -> UUID: ...


class SystemClock:
    """Default :class:`ClockPort` backed by :func:`datetime.now` (UTC)."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def _new_uuid7() -> UUID:
    import uuid_extensions

    return cast(UUID, uuid_extensions.uuid7())


class UuidV7Generator:
    """Default :class:`IdGeneratorPort` producing time-ordered UUIDv7 values."""

    def new(self) -> UUID:
        return _new_uuid7()
