"""Domain events emitted by entities and use cases.

These are plain data classes; the use case layer (or a transport adapter)
publishes them via the outbox / broker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

__all__ = [
    "ChangeEnriched",
    "ChangeNeedsEnrichment",
    "DomainEvent",
    "DriftRecommendationDetected",
    "SiteTemplateDriftDetected",
    "UrlBecameStale",
    "UrlChangeDetected",
    "UrlCrawlFailed",
]


def _nil_uuid() -> UUID:
    """Return the nil UUID ``00000000-0000-0000-0000-000000000000``."""
    return UUID(int=0)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base class for all domain events (carries envelope metadata)."""

    event_id: UUID
    occurred_at: datetime
    trace_id: UUID | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class UrlChangeDetected(DomainEvent):
    """Emitted when a meaningful change is detected for a URL."""

    url_id: UUID = field(default_factory=_nil_uuid)
    change_id: UUID = field(default_factory=_nil_uuid)
    domain_id: UUID = field(default_factory=_nil_uuid)
    category_id: UUID | None = None
    significant: bool = True


@dataclass(frozen=True, slots=True)
class UrlCrawlFailed(DomainEvent):
    """Emitted when a crawl attempt fails for a URL."""

    url_id: UUID = field(default_factory=_nil_uuid)
    domain_id: UUID = field(default_factory=_nil_uuid)
    category_id: UUID | None = None
    error: str = ""
    consecutive_errors: int = 0


@dataclass(frozen=True, slots=True)
class UrlBecameStale(DomainEvent):
    """Emitted when a URL has not changed and may be stale."""

    url_id: UUID = field(default_factory=_nil_uuid)
    domain_id: UUID = field(default_factory=_nil_uuid)
    category_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class SiteTemplateDriftDetected(DomainEvent):
    """Emitted when a site's DOM skeleton (template) changes between checks."""

    domain: str = ""
    url_pattern: str = ""
    profile_id: UUID = field(default_factory=_nil_uuid)
    old_template_hash: str = ""
    new_template_hash: str = ""
    old_version: int = 0
    new_version: int = 0
    sample_url: str = ""


@dataclass(frozen=True, slots=True)
class ChangeNeedsEnrichment(DomainEvent):
    """Emitted (AI tier only) when a change should be escalated to the LLM."""

    url_id: UUID = field(default_factory=_nil_uuid)
    change_id: UUID = field(default_factory=_nil_uuid)
    domain_id: UUID = field(default_factory=_nil_uuid)
    category_id: UUID | None = None
    template_class: str | None = None
    escalation_reasons: tuple[str, ...] = ()
    changed_zones: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ChangeEnriched(DomainEvent):
    """Emitted (AI tier only) when a change has been classified by the LLM."""

    url_id: UUID = field(default_factory=_nil_uuid)
    change_id: UUID = field(default_factory=_nil_uuid)
    domain_id: UUID = field(default_factory=_nil_uuid)
    category_id: UUID | None = None
    classification: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DriftRecommendationDetected(DomainEvent):
    """Emitted when recurring template drift is confirmed for a profile.

    Indicates a site redesign rather than content change; triggers a
    re-learn suggestion instead of repeated false-positive alerts.
    """

    domain: str = ""
    profile_id: UUID = field(default_factory=_nil_uuid)
    template_class: str | None = None
    drift_count: int = 0
