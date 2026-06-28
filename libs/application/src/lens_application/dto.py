"""Application-layer DTOs (decoupled from transport and ORM).

All DTOs are immutable Pydantic models. Use cases accept input DTOs and
return output DTOs; transport layers map these to/from their wire format.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CategoryDto",
    "ChangeDto",
    "ChangeEnrichedPayload",
    "ChannelBindingDto",
    "ChannelDto",
    "ClusterTemplatesResult",
    "ConflictPolicy",
    "CreateCategoryInput",
    "CreateChannelBindingInput",
    "CreateChannelInput",
    "CreateDomainInput",
    "CreateUrlInput",
    "DeadLetterMessage",
    "DeadLetterResult",
    "DomainDto",
    "EnqueueCheckResult",
    "EnqueueDueParams",
    "EnrichResult",
    "EvalPipelineResult",
    "EventEnvelope",
    "ExportResult",
    "HandleEventResult",
    "ImportResult",
    "LabelResult",
    "LearnZonesResult",
    "ListResult",
    "NotificationChannelOutcome",
    "RetentionResult",
    "SendTestNotificationResult",
    "SettingDto",
    "SettingUpdateInput",
    "SetupDto",
    "SnapshotDto",
    "TriggerCheckInput",
    "TriggerCheckResult",
    "UpdateCategoryInput",
    "UpdateChannelBindingInput",
    "UpdateChannelInput",
    "UpdateDomainInput",
    "UpdateUrlInput",
    "UrlDto",
]


class _DtoModel(BaseModel):
    """Frozen DTO base: forbid extras, validate defaults."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)


class ConflictPolicy(StrEnum):
    """How an import handles (domain, address) duplicates."""

    SKIP = "skip"
    MERGE = "merge"
    REPLACE = "replace"


class ListResult[T](_DtoModel):
    """A page of results with the cursor for the next page."""

    items: list[T] = Field(default_factory=list)
    next_cursor: str | None = None


class DomainDto(_DtoModel):
    id: UUID
    host: str
    display_name: str | None = None
    enabled: bool = True
    default_crawl_config: dict[str, Any] = Field(default_factory=dict)
    default_diff_config: dict[str, Any] = Field(default_factory=dict)
    politeness: dict[str, Any] = Field(default_factory=dict)
    default_routing: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CreateDomainInput(_DtoModel):
    host: str = Field(min_length=1)
    display_name: str | None = None
    enabled: bool = True
    default_crawl_config: dict[str, Any] | None = None
    default_diff_config: dict[str, Any] | None = None
    politeness: dict[str, Any] | None = None
    default_routing: dict[str, Any] | None = None


class UpdateDomainInput(_DtoModel):
    host: str | None = None
    display_name: str | None = None
    enabled: bool | None = None
    default_crawl_config: dict[str, Any] | None = None
    default_diff_config: dict[str, Any] | None = None
    politeness: dict[str, Any] | None = None
    default_routing: dict[str, Any] | None = None


class CategoryDto(_DtoModel):
    id: UUID
    domain_id: UUID
    name: str
    description: str | None = None
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class CreateCategoryInput(_DtoModel):
    domain_id: UUID
    name: str = Field(min_length=1)
    description: str | None = None
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None


class UpdateCategoryInput(_DtoModel):
    name: str | None = None
    description: str | None = None
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None


class UrlDto(_DtoModel):
    id: UUID
    domain_id: UUID
    category_id: UUID | None = None
    address: str
    enabled: bool = True
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None
    interval_seconds: int
    status: str
    last_checked_at: datetime | None = None
    next_due_at: datetime
    last_hash: str | None = None
    consecutive_errors: int = 0
    created_at: datetime
    updated_at: datetime


class CreateUrlInput(_DtoModel):
    domain_id: UUID
    address: str = Field(min_length=1)
    category_id: UUID | None = None
    enabled: bool = True
    interval_seconds: int = Field(ge=1)
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None


class UpdateUrlInput(_DtoModel):
    enabled: bool | None = None
    interval_seconds: int | None = None
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None


class ChannelDto(_DtoModel):
    id: UUID
    name: str
    kind: str
    enabled: bool = True
    has_secret: bool = False
    created_at: datetime
    updated_at: datetime


class CreateChannelInput(_DtoModel):
    name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    apprise_url: str = Field(min_length=1)
    enabled: bool = True


class UpdateChannelInput(_DtoModel):
    name: str | None = None
    kind: str | None = None
    apprise_url: str | None = None
    enabled: bool | None = None


class ChannelBindingDto(_DtoModel):
    id: UUID
    channel_id: UUID
    scope: str
    scope_id: UUID | None = None
    on_change: bool = True
    on_error: bool = False
    on_no_change: bool = False
    created_at: datetime


class CreateChannelBindingInput(_DtoModel):
    channel_id: UUID
    scope: str
    scope_id: UUID | None = None
    on_change: bool = True
    on_error: bool = False
    on_no_change: bool = False


class UpdateChannelBindingInput(_DtoModel):
    on_change: bool | None = None
    on_error: bool | None = None
    on_no_change: bool | None = None


class ImportResult(_DtoModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class ExportResult(_DtoModel):
    setup: SetupDto
    exported_at: datetime


class SetupDto(_DtoModel):
    """A self-contained import/export bundle (domains + categories + urls)."""

    version: int = 1
    domains: list[SetupDomain] = Field(default_factory=list)
    channels: list[ChannelDto] = Field(default_factory=list)
    bindings: list[ChannelBindingDto] = Field(default_factory=list)


class SetupDomain(_DtoModel):
    host: str
    display_name: str | None = None
    enabled: bool = True
    politeness: dict[str, Any] | None = None
    default_crawl_config: dict[str, Any] | None = None
    default_diff_config: dict[str, Any] | None = None
    default_routing: dict[str, Any] | None = None
    categories: list[SetupCategory] = Field(default_factory=list)


class SetupCategory(_DtoModel):
    name: str
    description: str | None = None
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None
    urls: list[SetupUrl] = Field(default_factory=list)


class SetupUrl(_DtoModel):
    address: str
    interval_seconds: int
    enabled: bool = True
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None


class TriggerCheckInput(_DtoModel):
    """Input for :class:`TriggerCheckUseCase`.

    Exactly one of ``url_id``, ``category_id``, or ``domain_id`` is required.
    """

    url_id: UUID | None = None
    category_id: UUID | None = None
    domain_id: UUID | None = None


class TriggerCheckResult(_DtoModel):
    """Output of :class:`TriggerCheckUseCase`."""

    enqueued: int = 0
    url_ids: list[UUID] = Field(default_factory=list)


class EnqueueCheckResult(_DtoModel):
    """Output of :class:`EnqueueDueUrlsUseCase`."""

    enqueued: int = 0
    url_ids: list[UUID] = Field(default_factory=list)


class ChangeDto(_DtoModel):
    id: UUID
    url_id: UUID
    previous_snapshot_id: UUID | None = None
    new_snapshot_id: UUID
    diff_ref: str | None = None
    added_count: int = 0
    removed_count: int = 0
    significant: bool = True
    created_at: datetime


class SnapshotDto(_DtoModel):
    id: UUID
    url_id: UUID
    content_ref: str
    content_hash: str
    http_status: int | None = None
    byte_size: int | None = None
    fetched_at: datetime


# ---------------------------------------------------------------------------
# Notification DTOs
# ---------------------------------------------------------------------------


class EventEnvelope(_DtoModel):
    """The on-the-wire shape of a domain event consumed by the notifier.

    The on-the-wire event envelope. ``message_id`` doubles as the outbox
    ``event_id`` and the notifier's dedup key.
    """

    message_id: UUID
    type: str
    occurred_at: datetime
    url_id: UUID
    domain_id: UUID
    category_id: UUID | None = None
    change_id: UUID | None = None
    significant: bool = True
    error: str | None = None
    consecutive_errors: int | None = None
    classification: dict[str, Any] | None = None


class NotificationChannelOutcome(_DtoModel):
    """A single per-channel send outcome.

    Carries enough information for the worker to emit a per-channel-kind
    Prometheus counter (``app="notifier"``) and to log a structured line
    with the channel identity and (optional) error.
    """

    channel_id: UUID
    channel_kind: str
    success: bool
    error: str | None = None


class HandleEventResult(_DtoModel):
    """Summary of one :class:`HandleChangeEventUseCase` run.

    The ``outcomes`` list carries per-channel send results in the order
    they were attempted, so the worker can emit
    ``notification_result_total{channel_kind=...}`` without losing the
    channel identity that the aggregate counts discard.
    """

    event_id: UUID
    delivered: int = 0
    skipped: int = 0
    failed: int = 0
    no_channels: bool = False
    outcomes: list[NotificationChannelOutcome] = Field(default_factory=list)
    suppressed: bool = False
    suppression_reason: str | None = None


class SendTestNotificationResult(_DtoModel):
    """Result of :class:`SendTestNotificationUseCase`."""

    channel_id: UUID
    channel_kind: str | None = None
    success: bool
    error: str | None = None


class EnqueueDueParams(_DtoModel):
    now: datetime | None = None
    batch_size: int = 100
    max_queue_depth: int | None = None


class DeadLetterMessage(_DtoModel):
    message_id: str
    queue: str
    body: dict[str, Any] = Field(default_factory=dict)
    attempts: int = 0
    last_error: str | None = None
    enqueued_at: datetime | None = None


class DeadLetterResult(_DtoModel):
    replayed: int = 0
    discarded: int = 0
    errors: list[str] = Field(default_factory=list)


class RetentionResult(_DtoModel):
    snapshots_evicted: int = 0
    blobs_deleted: int = 0
    orphan_blobs_deleted: int = 0
    errors: list[str] = Field(default_factory=list)


class SettingDto(_DtoModel):
    key: str
    value: Any
    immutable: bool = False
    role: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None


class SettingUpdateInput(_DtoModel):
    value: Any


# ---------------------------------------------------------------------------
# AI enrichment DTOs (12-ai-enrichment-layer.md section 2-5)
# ---------------------------------------------------------------------------


class EnrichResult(_DtoModel):
    """Output of :class:`EnrichChangeUseCase`."""

    change_id: UUID
    enrichment_status: str = "pending"
    escalation_reasons: list[str] = Field(default_factory=list)
    classification: dict[str, Any] | None = None
    enriched_event_emitted: bool = False


class ChangeEnrichedPayload(_DtoModel):
    """The on-the-wire shape of a ``ChangeEnriched`` event."""

    url_id: UUID
    change_id: UUID
    domain_id: UUID
    category_id: UUID | None = None
    classification: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Auto-learning DTOs (12-ai-enrichment-layer.md §6-§7)
# ---------------------------------------------------------------------------


class LearnZonesResult(_DtoModel):
    """Output of the ``learn-zones`` use case."""

    profile_id: UUID | None = None
    zone_selectors: list[dict[str, Any]] = Field(default_factory=list)
    noise_zones: list[str] = Field(default_factory=list)
    signal_zones: list[str] = Field(default_factory=list)
    observations_used: int = 0


class ClusterTemplatesResult(_DtoModel):
    """Output of the ``cluster-templates`` use case."""

    domain: str = ""
    clusters: list[dict[str, Any]] = Field(default_factory=list)
    drift_profiles: list[str] = Field(default_factory=list)
    urls_clustered: int = 0


class EvalPipelineResult(_DtoModel):
    """Output of the ``eval`` pipeline replay use case."""

    total_changes: int = 0
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    escalation_rate: float = 0.0
    fps_vs_lexical_only: float = 0.0
    per_class_distributions: dict[str, Any] = Field(default_factory=dict)


class LabelResult(_DtoModel):
    """Output of the ``label`` command / use case."""

    labeled: int = 0
    errors: list[str] = Field(default_factory=list)
