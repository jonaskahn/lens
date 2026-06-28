"""Shared mappers from domain entities to DTOs.

These are pure functions; they read the entity's value-object fields and
emit JSON-friendly dicts. They are the only place where domain shape
leaves the application layer.
"""

from __future__ import annotations

from typing import Any

from lens_application.dto import (
    CategoryDto,
    ChangeDto,
    ChannelBindingDto,
    ChannelDto,
    DomainDto,
    SnapshotDto,
    UrlDto,
)
from lens_domain.entities import (
    Category,
    Change,
    Channel,
    ChannelBinding,
    Domain,
    Snapshot,
    Url,
)
from lens_domain.value_objects import (
    CrawlConfig,
    DiffConfig,
    NotificationRouting,
    Politeness,
)


def _crawl_dict(c: CrawlConfig | None) -> dict[str, Any] | None:
    if c is None:
        return None
    return c.model_dump()


def _diff_dict(d: DiffConfig | None) -> dict[str, Any] | None:
    if d is None:
        return None
    return d.model_dump()


def _routing_dict(r: NotificationRouting | None) -> dict[str, Any] | None:
    if r is None:
        return None
    return r.to_dict()


def _politeness_dict(p: Politeness) -> dict[str, Any]:
    return p.model_dump()


def domain_to_dto(entity: Domain) -> DomainDto:
    return DomainDto(
        id=entity.id,
        host=entity.host.value,
        display_name=entity.display_name,
        enabled=entity.enabled,
        default_crawl_config=_crawl_dict(entity.default_crawl_config) or {},
        default_diff_config=_diff_dict(entity.default_diff_config) or {},
        politeness=_politeness_dict(entity.politeness),
        default_routing=_routing_dict(entity.default_routing) or {},
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def category_to_dto(entity: Category) -> CategoryDto:
    return CategoryDto(
        id=entity.id,
        domain_id=entity.domain_id.value,
        name=entity.name,
        description=entity.description,
        crawl_config=_crawl_dict(entity.crawl_config),
        diff_config=_diff_dict(entity.diff_config),
        routing=_routing_dict(entity.routing),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def url_to_dto(entity: Url) -> UrlDto:
    return UrlDto(
        id=entity.id,
        domain_id=entity.domain_id.value,
        category_id=entity.category_id.value if entity.category_id else None,
        address=entity.address.value,
        enabled=entity.enabled,
        crawl_config=_crawl_dict(entity.crawl_config),
        diff_config=_diff_dict(entity.diff_config),
        routing=_routing_dict(entity.routing),
        interval_seconds=entity.interval.seconds,
        status=entity.status.value,
        last_checked_at=entity.last_checked_at,
        next_due_at=entity.next_due_at,
        last_hash=entity.last_hash,
        consecutive_errors=entity.consecutive_errors,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def channel_to_dto(entity: Channel, *, has_secret: bool = True) -> ChannelDto:
    return ChannelDto(
        id=entity.id,
        name=entity.name,
        kind=entity.kind.value,
        enabled=entity.enabled,
        has_secret=has_secret,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def channel_binding_to_dto(entity: ChannelBinding) -> ChannelBindingDto:
    return ChannelBindingDto(
        id=entity.id,
        channel_id=entity.channel_id,
        scope=entity.scope.value,
        scope_id=entity.scope_id,
        on_change=entity.on_change,
        on_error=entity.on_error,
        on_no_change=entity.on_no_change,
        created_at=entity.created_at,
    )


def change_to_dto(entity: Change) -> ChangeDto:
    return ChangeDto(
        id=entity.id,
        url_id=entity.url_id.value,
        previous_snapshot_id=(entity.previous_snapshot_id.value if entity.previous_snapshot_id is not None else None),
        new_snapshot_id=entity.new_snapshot_id.value,
        diff_ref=entity.diff_ref,
        added_count=entity.diff_summary.added_count,
        removed_count=entity.diff_summary.removed_count,
        significant=entity.significant,
        created_at=entity.created_at,
    )


def snapshot_to_dto(entity: Snapshot) -> SnapshotDto:
    return SnapshotDto(
        id=entity.id,
        url_id=entity.url_id.value,
        content_ref=entity.content_ref,
        content_hash=entity.content_hash.hex,
        http_status=entity.http_status,
        byte_size=entity.byte_size,
        fetched_at=entity.fetched_at,
    )
