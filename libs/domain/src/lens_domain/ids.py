"""Strongly-typed identifier value objects.

All ids are UUIDv7-generated :class:`uuid.UUID` values. The wrapper types
prevent accidentally passing a :class:`UrlId` where a :class:`DomainId` is
expected at the type-checker level.
"""

from __future__ import annotations

from uuid import UUID

__all__ = [
    "CategoryId",
    "ChangeId",
    "DomainId",
    "ProfileId",
    "SnapshotId",
    "UrlId",
]


class DomainId:
    """Identifier for a :class:`Domain` aggregate root."""

    __slots__ = ("_value",)

    def __init__(self, value: UUID) -> None:
        self._value = value

    @property
    def value(self) -> UUID:
        return self._value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DomainId) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"DomainId({self._value!s})"

    def __str__(self) -> str:
        return str(self._value)


class CategoryId:
    """Identifier for a :class:`Category` entity."""

    __slots__ = ("_value",)

    def __init__(self, value: UUID) -> None:
        self._value = value

    @property
    def value(self) -> UUID:
        return self._value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CategoryId) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"CategoryId({self._value!s})"

    def __str__(self) -> str:
        return str(self._value)


class UrlId:
    """Identifier for a :class:`Url` aggregate root."""

    __slots__ = ("_value",)

    def __init__(self, value: UUID) -> None:
        self._value = value

    @property
    def value(self) -> UUID:
        return self._value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, UrlId) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"UrlId({self._value!s})"

    def __str__(self) -> str:
        return str(self._value)


class SnapshotId:
    """Identifier for a :class:`lens_domain.entities.Snapshot` row."""

    __slots__ = ("_value",)

    def __init__(self, value: UUID) -> None:
        self._value = value

    @property
    def value(self) -> UUID:
        return self._value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SnapshotId) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"SnapshotId({self._value!s})"

    def __str__(self) -> str:
        return str(self._value)


class ProfileId:
    """Identifier for a :class:`lens_domain.entities.SiteProfile` entity."""

    __slots__ = ("_value",)

    def __init__(self, value: UUID) -> None:
        self._value = value

    @property
    def value(self) -> UUID:
        return self._value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ProfileId) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"ProfileId({self._value!s})"

    def __str__(self) -> str:
        return str(self._value)


class ChangeId:
    """Identifier for a :class:`lens_domain.entities.Change` row."""

    __slots__ = ("_value",)

    def __init__(self, value: UUID) -> None:
        self._value = value

    @property
    def value(self) -> UUID:
        return self._value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ChangeId) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __repr__(self) -> str:
        return f"ChangeId({self._value!s})"

    def __str__(self) -> str:
        return str(self._value)
