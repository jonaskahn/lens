"""Domain-layer exception hierarchy and concrete error types.

Re-uses :class:`lens_common.errors.DomainError` as the root so the application
layer can catch the architectural root and the transport layer can map to
HTTP/broker codes uniformly.
"""

from __future__ import annotations

from lens_common.errors import DomainError

__all__ = [
    "DomainError",
    "DuplicateCategory",
    "DuplicateDomain",
    "DuplicateUrl",
    "HostMismatch",
    "InvalidAddress",
    "InvalidHostname",
    "InvalidInterval",
    "InvalidPoliteness",
    "InvalidScope",
    "InvalidStateTransition",
    "NoChannelsBound",
]


class InvalidHostname(DomainError):
    """A hostname fails syntactic or normalisation rules."""


class InvalidAddress(DomainError):
    """A URL address is not absolute or has an unsupported scheme."""


class HostMismatch(DomainError):
    """The URL address host does not match the enclosing domain host."""


class DuplicateDomain(DomainError):
    """A domain with the same host already exists."""


class DuplicateCategory(DomainError):
    """A category with the same name already exists within the domain."""


class DuplicateUrl(DomainError):
    """A URL with the same address already exists within the domain."""


class InvalidInterval(DomainError):
    """An interval violates the global or per-domain minimum."""


class InvalidPoliteness(DomainError):
    """A politeness value fails constraints (negative, below floor)."""


class InvalidScope(DomainError):
    """A scope/scope-id combination is not allowed (e.g. global with id)."""


class InvalidStateTransition(DomainError):
    """A :class:`Url` state-machine transition was attempted from the wrong state."""


class NoChannelsBound(DomainError):
    """Notification routing found no :class:`ChannelBinding` for the resolved scope."""
