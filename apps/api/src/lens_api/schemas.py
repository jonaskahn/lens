"""Pydantic schemas for HTTP request/response (decoupled from ORM/DTO)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ApiKeyCreateRequest",
    "ApiKeyCreateResponse",
    "ApiKeyListItem",
    "CategoryCreate",
    "CategoryResponse",
    "CategoryUpdate",
    "ChangeEnrichmentResponse",
    "ChangeResponse",
    "ChannelBindingCreate",
    "ChannelBindingResponse",
    "ChannelBindingUpdate",
    "ChannelCreate",
    "ChannelResponse",
    "ChannelUpdate",
    "DeadLetterItem",
    "DeadLetterResultResponse",
    "DomainCreate",
    "DomainResponse",
    "DomainUpdate",
    "ErrorResponse",
    "HealthStatusResponse",
    "ImportRequest",
    "ImportResponse",
    "ListResponse",
    "RetentionRunResponse",
    "SettingPutRequest",
    "SettingResponse",
    "SnapshotListResponse",
    "SnapshotResponse",
    "TriggerCheckResponse",
    "UrlCreate",
    "UrlResponse",
    "UrlUpdate",
]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


class DomainCreate(_Base):
    host: str = Field(min_length=1, max_length=253)
    display_name: str | None = None
    enabled: bool = True
    default_crawl_config: dict[str, Any] | None = None
    default_diff_config: dict[str, Any] | None = None
    politeness: dict[str, Any] | None = None
    default_routing: dict[str, Any] | None = None


class DomainUpdate(_Base):
    host: str | None = None
    display_name: str | None = None
    enabled: bool | None = None
    default_crawl_config: dict[str, Any] | None = None
    default_diff_config: dict[str, Any] | None = None
    politeness: dict[str, Any] | None = None
    default_routing: dict[str, Any] | None = None


class DomainResponse(_Base):
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


class CategoryCreate(_Base):
    name: str = Field(min_length=1)
    description: str | None = None
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None


class CategoryUpdate(_Base):
    name: str | None = None
    description: str | None = None
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None


class CategoryResponse(_Base):
    id: UUID
    domain_id: UUID
    name: str
    description: str | None = None
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class UrlCreate(_Base):
    domain_id: UUID
    address: str = Field(min_length=1)
    category_id: UUID | None = None
    enabled: bool = True
    interval_seconds: int = Field(ge=1)
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None


class UrlUpdate(_Base):
    enabled: bool | None = None
    interval_seconds: int | None = None
    crawl_config: dict[str, Any] | None = None
    diff_config: dict[str, Any] | None = None
    routing: dict[str, Any] | None = None


class UrlResponse(_Base):
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


class ChannelCreate(_Base):
    name: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    apprise_url: str = Field(min_length=1)
    enabled: bool = True


class ChannelUpdate(_Base):
    name: str | None = None
    kind: str | None = None
    apprise_url: str | None = None
    enabled: bool | None = None


class ChannelResponse(_Base):
    id: UUID
    name: str
    kind: str
    enabled: bool = True
    has_secret: bool = False
    created_at: datetime
    updated_at: datetime


class ChannelBindingCreate(_Base):
    channel_id: UUID
    scope: str
    scope_id: UUID | None = None
    on_change: bool = True
    on_error: bool = False
    on_no_change: bool = False


class ChannelBindingUpdate(_Base):
    on_change: bool | None = None
    on_error: bool | None = None
    on_no_change: bool | None = None


class ChannelBindingResponse(_Base):
    id: UUID
    channel_id: UUID
    scope: str
    scope_id: UUID | None = None
    on_change: bool = True
    on_error: bool = False
    on_no_change: bool = False
    created_at: datetime


class ListResponse[T](_Base):
    items: list[T] = Field(default_factory=list)
    next_cursor: str | None = None


class ImportRequest(_Base):
    setup: dict[str, Any]
    on_conflict: str = "skip"


class ImportResponse(_Base):
    created: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


class ErrorResponse(_Base):
    error: dict[str, Any]


class TriggerCheckResponse(_Base):
    enqueued: int
    url_ids: list[UUID]


class ChangeResponse(_Base):
    id: UUID
    url_id: UUID
    previous_snapshot_id: UUID | None = None
    new_snapshot_id: UUID
    diff_ref: str | None = None
    added_count: int = 0
    removed_count: int = 0
    significant: bool = True
    created_at: datetime


class SnapshotResponse(_Base):
    id: UUID
    url_id: UUID
    content_ref: str
    content_hash: str
    http_status: int | None = None
    byte_size: int | None = None
    fetched_at: datetime


class SnapshotListResponse(_Base):
    items: list[SnapshotResponse] = Field(default_factory=list)


class HealthStatusResponse(_Base):
    healthy: bool
    components: dict[str, dict[str, Any]] = Field(default_factory=dict)


class DeadLetterItem(_Base):
    message_id: str
    queue: str
    body: dict[str, Any] = Field(default_factory=dict)
    attempts: int = 0
    last_error: str | None = None


class DeadLetterResultResponse(_Base):
    replayed: int = 0
    discarded: int = 0
    errors: list[str] = Field(default_factory=list)


class SettingPutRequest(_Base):
    value: Any


class SettingResponse(_Base):
    key: str
    value: Any
    immutable: bool = False
    role: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None


class RetentionRunResponse(_Base):
    snapshots_evicted: int = 0
    blobs_deleted: int = 0
    orphan_blobs_deleted: int = 0


class ChangeEnrichmentResponse(_Base):
    """AI enrichment classification data for a change (L6 LLM tier)."""

    change_id: UUID
    change_type: str
    is_meaningful: bool
    severity: int
    summary: str
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    confidence: float
    model_id: str


class ApiKeyCreateRequest(_Base):
    name: str = Field(min_length=1, max_length=200)
    scopes: list[str] = Field(default_factory=lambda: ["read"])
    enabled: bool = True


class ApiKeyCreateResponse(_Base):
    """Returned exactly once on create; the plaintext is not stored."""

    id: UUID
    name: str
    plaintext: str
    scopes: list[str] = Field(default_factory=list)
    enabled: bool = True


class ApiKeyListItem(_Base):
    id: UUID
    name: str
    scopes: list[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: datetime | None = None
