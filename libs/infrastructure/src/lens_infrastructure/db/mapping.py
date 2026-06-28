"""Mappers between SQLAlchemy rows and domain entities.

Keeps ORM types out of the domain layer and domain types out of the ORM.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from lens_application.pipeline import StoredCheckState
from lens_domain.entities import (
    Category,
    Change,
    Channel,
    ChannelBinding,
    Domain,
    SiteProfile,
    Snapshot,
    Url,
)
from lens_domain.enums import BindingScope, ChannelKind, UrlStatus
from lens_domain.ids import (
    CategoryId,
    ChangeId,
    DomainId,
    ProfileId,
    SnapshotId,
    UrlId,
)
from lens_domain.value_objects import (
    Address,
    ContentHash,
    CrawlConfig,
    DiffConfig,
    DiffSummary,
    Hostname,
    Interval,
    NotificationRouting,
    Politeness,
    SignificanceRule,
    ZoneSelector,
)
from lens_infrastructure.db.models import (
    CategoryModel,
    ChangeModel,
    ChannelBindingModel,
    ChannelModel,
    DomainModel,
    OutboxModel,
    SiteProfileModel,
    SnapshotModel,
    UrlCheckStateModel,
    UrlModel,
)
from lens_infrastructure.secrets import SecretCipher

__all__ = [
    "category_from_model",
    "category_to_model",
    "change_from_model",
    "change_to_model",
    "channel_binding_from_model",
    "channel_binding_to_model",
    "channel_from_model",
    "channel_to_model",
    "domain_from_model",
    "domain_to_model",
    "outbox_from_model",
    "outbox_to_model",
    "snapshot_from_model",
    "snapshot_to_model",
    "url_check_state_from_model",
    "url_from_model",
    "url_to_model",
]


_cipher: SecretCipher | None = None


def set_secret_cipher(cipher: SecretCipher | None) -> None:
    """Configure the cipher used for ``Channel.apprise_url`` encryption.

    Tests that do not care about encryption pass ``None`` and the channel
    mapper round-trips the URL as utf-8 bytes (matching the legacy
    no-cipher behaviour for the in-memory suite). Production composition
    roots install a
    :class:`FernetSecretCipher` before the first channel is persisted.
    """
    global _cipher
    _cipher = cipher


def _crawl_from(value: dict[str, Any] | None) -> CrawlConfig | None:
    if value is None:
        return None
    return CrawlConfig(**value)


def _diff_from(value: dict[str, Any] | None) -> DiffConfig | None:
    if value is None:
        return None
    return DiffConfig(**value)


def _routing_from(value: dict[str, Any] | None) -> NotificationRouting | None:
    if value is None:
        return None
    from lens_domain.enums import TriggerType

    triggers = {TriggerType(t) for t in value.get("triggers", [])}
    return NotificationRouting(channel_ids=list(value.get("channel_ids", [])), triggers=triggers)


def _politeness_from(value: dict[str, Any] | None) -> Politeness:
    if value is None:
        return Politeness()
    return Politeness(**value)


def domain_to_model(entity: Domain) -> DomainModel:
    return DomainModel(
        id=entity.id,
        host=entity.host.value,
        display_name=entity.display_name,
        enabled=entity.enabled,
        default_crawl_config=entity.default_crawl_config.model_dump(),
        default_diff_config=entity.default_diff_config.model_dump(),
        politeness=entity.politeness.model_dump(),
        default_routing=entity.default_routing.to_dict(),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def domain_from_model(model: DomainModel) -> Domain:
    return Domain(
        id=DomainId(model.id),
        host=Hostname(value=model.host),
        display_name=model.display_name,
        enabled=model.enabled,
        default_crawl_config=_crawl_from(model.default_crawl_config),
        default_diff_config=_diff_from(model.default_diff_config),
        politeness=_politeness_from(model.politeness),
        default_routing=_routing_from(model.default_routing),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def category_to_model(entity: Category) -> CategoryModel:
    return CategoryModel(
        id=entity.id,
        domain_id=entity.domain_id.value,
        name=entity.name,
        description=entity.description,
        crawl_config=entity.crawl_config.model_dump() if entity.crawl_config else None,
        diff_config=entity.diff_config.model_dump() if entity.diff_config else None,
        routing=entity.routing.to_dict() if entity.routing else None,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def category_from_model(model: CategoryModel) -> Category:
    return Category(
        id=CategoryId(model.id),
        domain_id=DomainId(model.domain_id),
        name=model.name,
        description=model.description,
        crawl_config=_crawl_from(model.crawl_config),
        diff_config=_diff_from(model.diff_config),
        routing=_routing_from(model.routing),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def url_to_model(entity: Url) -> UrlModel:
    return UrlModel(
        id=entity.id,
        domain_id=entity.domain_id.value,
        category_id=entity.category_id.value if entity.category_id else None,
        address=entity.address.value,
        enabled=entity.enabled,
        crawl_config=entity.crawl_config.model_dump() if entity.crawl_config else None,
        diff_config=entity.diff_config.model_dump() if entity.diff_config else None,
        routing=entity.routing.to_dict() if entity.routing else None,
        interval_seconds=entity.interval.seconds,
        status=entity.status.value,
        last_checked_at=entity.last_checked_at,
        next_due_at=entity.next_due_at,
        last_hash=entity.last_hash,
        consecutive_errors=entity.consecutive_errors,
        locked_by=entity.locked_by,
        lock_expires_at=entity.lock_expires_at,
        enqueued_at=entity.enqueued_at,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def url_from_model(model: UrlModel) -> Url:
    interval = Interval(seconds=model.interval_seconds, global_minimum=1)
    return Url(
        id=UrlId(model.id),
        domain_id=DomainId(model.domain_id),
        address=Address(value=model.address),
        interval=interval,
        category_id=CategoryId(model.category_id) if model.category_id else None,
        enabled=model.enabled,
        crawl_config=_crawl_from(model.crawl_config),
        diff_config=_diff_from(model.diff_config),
        routing=_routing_from(model.routing),
        status=UrlStatus(model.status),
        last_checked_at=model.last_checked_at,
        next_due_at=model.next_due_at,
        last_hash=model.last_hash,
        consecutive_errors=model.consecutive_errors,
        locked_by=model.locked_by,
        lock_expires_at=model.lock_expires_at,
        enqueued_at=model.enqueued_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def channel_to_model(entity: Channel) -> ChannelModel:
    apprise_url_bytes = entity.apprise_url.encode("utf-8") if _cipher is None else _cipher.encrypt(entity.apprise_url)
    return ChannelModel(
        id=entity.id,
        name=entity.name,
        kind=entity.kind.value,
        apprise_url_encrypted=apprise_url_bytes,
        enabled=entity.enabled,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def channel_from_model(model: ChannelModel) -> Channel:
    if _cipher is None:
        apprise_url = model.apprise_url_encrypted.decode("utf-8")
    else:
        apprise_url = _cipher.decrypt(model.apprise_url_encrypted)
    return Channel(
        id=model.id,
        name=model.name,
        kind=ChannelKind(model.kind),
        apprise_url=apprise_url,
        enabled=model.enabled,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def channel_binding_to_model(entity: ChannelBinding) -> ChannelBindingModel:
    return ChannelBindingModel(
        id=entity.id,
        channel_id=entity.channel_id,
        scope=entity.scope.value,
        scope_id=entity.scope_id,
        on_change=entity.on_change,
        on_error=entity.on_error,
        on_no_change=entity.on_no_change,
        created_at=entity.created_at,
    )


def channel_binding_from_model(model: ChannelBindingModel) -> ChannelBinding:
    return ChannelBinding(
        id=model.id,
        channel_id=model.channel_id,
        scope=BindingScope(model.scope),
        scope_id=model.scope_id,
        on_change=model.on_change,
        on_error=model.on_error,
        on_no_change=model.on_no_change,
        created_at=model.created_at,
    )


def snapshot_to_model(entity: Snapshot) -> SnapshotModel:
    return SnapshotModel(
        id=entity.id,
        url_id=entity.url_id.value,
        content_ref=entity.content_ref,
        content_hash=entity.content_hash.hex,
        http_status=entity.http_status,
        byte_size=entity.byte_size,
        fetched_at=entity.fetched_at,
        created_at=entity.created_at,
    )


def snapshot_from_model(model: SnapshotModel) -> Snapshot:
    return Snapshot(
        id=SnapshotId(model.id),
        url_id=UrlId(model.url_id),
        content_ref=model.content_ref,
        content_hash=ContentHash(hex=model.content_hash),
        http_status=model.http_status,
        byte_size=model.byte_size,
        fetched_at=model.fetched_at,
        created_at=model.created_at,
    )


def change_to_model(entity: Change) -> ChangeModel:
    return ChangeModel(
        id=entity.id,
        url_id=entity.url_id.value,
        previous_snapshot_id=entity.previous_snapshot_id.value if entity.previous_snapshot_id is not None else None,
        new_snapshot_id=entity.new_snapshot_id.value,
        diff_ref=entity.diff_ref,
        added_count=entity.diff_summary.added_count,
        removed_count=entity.diff_summary.removed_count,
        semantic_score=entity.semantic_score,
        significant=entity.significant,
        enrichment_status=getattr(entity, "enrichment_status", "pending"),
        created_at=entity.created_at,
    )


def change_from_model(model: ChangeModel) -> Change:
    return Change(
        id=ChangeId(model.id),
        url_id=UrlId(model.url_id),
        new_snapshot_id=SnapshotId(model.new_snapshot_id),
        previous_snapshot_id=SnapshotId(model.previous_snapshot_id) if model.previous_snapshot_id is not None else None,
        diff_ref=model.diff_ref,
        diff_summary=DiffSummary(
            added_count=model.added_count,
            removed_count=model.removed_count,
        ),
        semantic_score=model.semantic_score,
        significant=model.significant,
        enrichment_status=model.enrichment_status,
        created_at=model.created_at,
    )


def url_check_state_to_model(state: StoredCheckState) -> UrlCheckStateModel:
    return UrlCheckStateModel(
        url_id=state.url_id,
        raw_md5=state.raw_md5,
        filter_config_hash=state.filter_config_hash,
        last_etag=state.last_etag,
        last_modified=state.last_modified,
        zone_hashes=dict(state.zone_hashes),
        zone_texts=dict(state.zone_texts),
        previous_cleaned_text=state.previous_cleaned_text,
        last_check_at=state.last_check_at,
        profile_id=state.profile_id,
    )


def url_check_state_from_model(model: UrlCheckStateModel) -> StoredCheckState:
    return StoredCheckState(
        url_id=model.url_id,
        raw_md5=model.raw_md5,
        filter_config_hash=model.filter_config_hash,
        last_etag=model.last_etag,
        last_modified=model.last_modified,
        zone_hashes=dict(model.zone_hashes or {}),
        zone_texts=dict(model.zone_texts or {}),
        previous_cleaned_text=model.previous_cleaned_text or "",
        last_check_at=model.last_check_at,
        profile_id=model.profile_id,
    )


def outbox_to_model(
    *,
    id: UUID,
    aggregate_type: str,
    aggregate_id: UUID,
    event_type: str,
    event_id: UUID,
    payload: dict[str, Any],
    created_at: datetime,
) -> OutboxModel:
    return OutboxModel(
        id=id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        event_id=event_id,
        payload=payload,
        created_at=created_at,
    )


def outbox_from_model(model: OutboxModel) -> dict[str, Any]:
    return {
        "id": model.id,
        "aggregate_type": model.aggregate_type,
        "aggregate_id": model.aggregate_id,
        "event_type": model.event_type,
        "event_id": model.event_id,
        "payload": dict(model.payload),
        "created_at": model.created_at,
        "sent_at": model.sent_at,
        "attempts": model.attempts,
    }


def site_profile_to_model(profile: SiteProfile) -> dict[str, Any]:
    zone_data = [
        {
            "name": z.name,
            "css_selector": z.css_selector,
            "weight": z.weight,
            "is_noise": z.is_noise,
        }
        for z in profile.zone_selectors
    ]
    rule_data = [
        {
            "type": r.type.value,
            "pattern": r.pattern,
            "is_regex": r.is_regex,
        }
        for r in profile.significance_rules
    ]
    return {
        "id": profile.id,
        "domain": profile.domain,
        "url_pattern": profile.url_pattern,
        "template_hash": profile.template_hash,
        "template_class": profile.template_class,
        "zone_selectors": zone_data,
        "significance_rules": rule_data,
        "semantic_threshold": profile.semantic_threshold,
        "version": profile.version,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def site_profile_from_model(
    row: SiteProfileModel,
    *,
    now: datetime,
) -> SiteProfile:
    raw_zones: list[dict[str, Any]] = list(row.zone_selectors) if row.zone_selectors else []
    zones = [
        ZoneSelector(
            name=z["name"],
            css_selector=z["css_selector"],
            weight=float(z.get("weight", 1.0)),
            is_noise=bool(z.get("is_noise", False)),
        )
        for z in raw_zones
    ]
    raw_rules: list[dict[str, Any]] = list(row.significance_rules) if row.significance_rules else []
    rules = [
        SignificanceRule(
            type=r["type"],
            pattern=r["pattern"],
            is_regex=bool(r.get("is_regex", False)),
        )
        for r in raw_rules
    ]
    return SiteProfile(
        id=ProfileId(row.id),
        domain=row.domain,
        url_pattern=row.url_pattern,
        template_hash=row.template_hash,
        template_class=row.template_class,
        zone_selectors=zones,
        significance_rules=rules,
        semantic_threshold=float(row.semantic_threshold),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
