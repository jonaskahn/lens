"""Shared typing primitives: pagination, id aliases, small helpers."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

__all__ = [
    "CorrelationId",
    "Id",
    "Page",
    "PageRequest",
]


T = TypeVar("T")

Id = UUID
"""Canonical alias for any primary-key identifier in the system (UUIDv7)."""

CorrelationId = UUID
"""Correlation identifier propagated across logs, broker, and HTTP requests."""


@dataclass(frozen=True, slots=True)
class PageRequest:
    """Cursor-style pagination request.

    ``cursor`` is an opaque token returned by the previous page (or ``None`` for
    the first page). ``limit`` is the maximum number of items to return.
    """

    cursor: str | None = None
    limit: int = 50


@dataclass(frozen=True, slots=True)
class Page[T]:
    """A single page of results plus the cursor for the next page."""

    items: list[T]
    next_cursor: str | None

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)
