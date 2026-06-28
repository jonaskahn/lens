"""SQLAlchemy ORM models for every core table.

Tables cover ``domains``, ``categories``, ``urls``, ``channels``,
``channel_bindings``, ``api_keys``, ``snapshots``, ``changes``,
``outbox``, ``notification_log``, and ``site_profiles``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lens_infrastructure.db.base import Base

__all__ = [
    "ApiKeyModel",
    "CategoryModel",
    "ChangeClassificationModel",
    "ChangeLabelModel",
    "ChangeModel",
    "ChannelBindingModel",
    "ChannelModel",
    "DomainModel",
    "NotificationLogModel",
    "OutboxModel",
    "SiteProfileModel",
    "SnapshotModel",
    "UrlCheckStateModel",
    "UrlModel",
    "ZoneEmbeddingModel",
]


class DomainModel(Base):
    __tablename__ = "domains"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    host: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    default_crawl_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    default_diff_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    politeness: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    default_routing: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    categories: Mapped[list[CategoryModel]] = relationship(
        back_populates="domain",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    urls: Mapped[list[UrlModel]] = relationship(
        back_populates="domain",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CategoryModel(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("domain_id", "name", name="uq_categories_domain_name"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    domain_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    crawl_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    diff_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    routing: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    domain: Mapped[DomainModel] = relationship(back_populates="categories")
    urls: Mapped[list[UrlModel]] = relationship(
        back_populates="category",
        passive_deletes=True,
    )


class UrlModel(Base):
    __tablename__ = "urls"
    __table_args__ = (
        UniqueConstraint("domain_id", "address", name="uq_urls_domain_address"),
        CheckConstraint(
            "status IN ('idle','enqueued','crawling','error','disabled')",
            name="ck_urls_status",
        ),
        Index(
            "idx_urls_due",
            "next_due_at",
            postgresql_where=text("status = 'idle' AND enabled"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    domain_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    address: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    crawl_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    diff_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    routing: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'idle'"))
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    last_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_errors: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    locked_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    lock_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    enqueued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    domain: Mapped[DomainModel] = relationship(back_populates="urls")
    category: Mapped[CategoryModel | None] = relationship(back_populates="urls")


class ChannelModel(Base):
    __tablename__ = "channels"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('email','slack','discord','telegram','webhook')",
            name="ck_channels_kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    apprise_url_encrypted: Mapped[bytes] = mapped_column(nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ChannelBindingModel(Base):
    __tablename__ = "channel_bindings"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('global','domain','category','url')",
            name="ck_channel_bindings_scope",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    channel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    scope_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    on_change: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    on_error: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    on_no_change: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ApiKeyModel(Base):
    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    scopes: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{read}'"),
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class SnapshotModel(Base):
    __tablename__ = "snapshots"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    url_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("urls.id", ondelete="CASCADE"),
        nullable=False,
    )
    content_ref: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ChangeModel(Base):
    __tablename__ = "changes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    url_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("urls.id", ondelete="CASCADE"),
        nullable=False,
    )
    previous_snapshot_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    new_snapshot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("snapshots.id", ondelete="CASCADE"),
        nullable=False,
    )
    diff_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    removed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    semantic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    significant: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    enrichment_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
        comment="pending|enriched|failed — set by crawler (pending) or ai_worker (enriched/failed).",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class OutboxModel(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        Index(
            "idx_outbox_unsent",
            "created_at",
            postgresql_where=text("sent_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(Text, nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        unique=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class NotificationLogModel(Base):
    """One row per ``(event_id, channel_id)`` delivery, with a unique
    constraint providing dedup."""

    __tablename__ = "notification_log"
    __table_args__ = (
        UniqueConstraint("event_id", "channel_id", name="uq_notification_log_event_channel"),
        CheckConstraint(
            "status IN ('sent','failed')",
            name="ck_notification_log_status",
        ),
        Index("idx_notification_log_event", "event_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    channel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class SiteProfileModel(Base):
    __tablename__ = "site_profiles"

    __table_args__ = (
        Index("idx_site_profiles_domain_pattern", "domain", "url_pattern"),
        Index("idx_site_profiles_template_class", "template_class"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    url_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    template_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    zone_selectors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    significance_rules: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    semantic_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0.05"),
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


# ---------------------------------------------------------------------------
# AI enrichment tables (12-ai-enrichment-layer.md)
# ---------------------------------------------------------------------------


class ChangeClassificationModel(Base):
    """One LLM-produced classification per change (unique on ``change_id``)."""

    __tablename__ = "change_classifications"
    __table_args__ = (
        UniqueConstraint(
            "change_id",
            name="uq_change_classifications_change_id",
        ),
        Index("idx_change_classifications_change_type", "change_type"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    change_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("changes.id", ondelete="CASCADE"),
        nullable=False,
    )
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    is_meaningful: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    severity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1"),
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        server_default=text("0.0"),
    )
    model_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    llm_latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ZoneEmbeddingModel(Base):
    """Durable cache of embedding vectors keyed by ``(model_id, text_hash)``."""

    __tablename__ = "zone_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "model_id",
            "text_hash",
            name="uq_zone_embeddings_model_text",
        ),
        Index("idx_zone_embeddings_model_text", "model_id", "text_hash"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    vector: Mapped[list[float]] = mapped_column(
        ARRAY(DOUBLE_PRECISION),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


# ---------------------------------------------------------------------------
# Auto-learning tables (12-ai-enrichment-layer.md §6-§7)
# ---------------------------------------------------------------------------


class ChangeLabelModel(Base):
    """One label per ``(change_id, labeled_by)`` pair."""

    __tablename__ = "change_labels"
    __table_args__ = (
        UniqueConstraint(
            "change_id",
            "labeled_by",
            name="uq_change_labels_change_labeled_by",
        ),
        Index("idx_change_labels_change", "change_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    change_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("changes.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_change: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    is_meaningful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    change_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    labeled_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class UrlCheckStateModel(Base):
    """One row per URL holding the prior-check state.

    Powers the L0/L1 short-circuits and the previous-cleaned-text diff
    on the next crawl. The URL identity is the primary key, so writes
    are idempotent.
    """

    __tablename__ = "url_check_states"

    url_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("urls.id", ondelete="CASCADE"),
        primary_key=True,
    )
    raw_md5: Mapped[str | None] = mapped_column(Text, nullable=True)
    filter_config_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_modified: Mapped[str | None] = mapped_column(Text, nullable=True)
    zone_hashes: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    zone_texts: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    previous_cleaned_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("''"),
    )
    last_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    profile_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
