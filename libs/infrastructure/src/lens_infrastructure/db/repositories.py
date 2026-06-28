"""SQLAlchemy repository implementations for every entity.

Each repository implements its application-layer port using a
:class:`sqlalchemy.orm.Session`. The repositories never touch I/O outside of
the session; the session is supplied by :class:`SqlAlchemyUnitOfWork`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lens_application.errors import ConflictError
from lens_application.pipeline import SiteProfileRepository, StoredCheckState
from lens_application.ports import (
    CategoryRepository,
    ChangeRepository,
    ChannelBindingRepository,
    ChannelRepository,
    DomainRepository,
    NotificationLogRepository,
    OutboxRepository,
    SnapshotRepository,
    UrlCheckStateRepository,
    UrlRepository,
)
from lens_common.ports import UuidV7Generator
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
from lens_domain.enums import UrlStatus
from lens_domain.value_objects import ChangeLabel
from lens_infrastructure.db.mapping import (
    category_from_model,
    category_to_model,
    change_from_model,
    change_to_model,
    channel_binding_from_model,
    channel_binding_to_model,
    channel_from_model,
    channel_to_model,
    domain_from_model,
    domain_to_model,
    outbox_to_model,
    site_profile_from_model,
    site_profile_to_model,
    snapshot_from_model,
    snapshot_to_model,
    url_check_state_from_model,
    url_check_state_to_model,
    url_from_model,
    url_to_model,
)
from lens_infrastructure.db.models import (
    CategoryModel,
    ChangeLabelModel,
    ChangeModel,
    ChannelBindingModel,
    ChannelModel,
    DomainModel,
    NotificationLogModel,
    OutboxModel,
    SiteProfileModel,
    SnapshotModel,
    UrlCheckStateModel,
    UrlModel,
)

__all__ = [
    "SqlAlchemyCategoryRepository",
    "SqlAlchemyChangeRepository",
    "SqlAlchemyChannelBindingRepository",
    "SqlAlchemyChannelRepository",
    "SqlAlchemyDomainRepository",
    "SqlAlchemyNotificationLogRepository",
    "SqlAlchemyOutboxRepository",
    "SqlAlchemySnapshotRepository",
    "SqlAlchemyUrlCheckStateRepository",
    "SqlAlchemyUrlRepository",
    "SqlChangeClassificationRepository",
    "SqlChangeLabelRepository",
]


def _cursor_after(items: Sequence[Any], cursor: str | None, limit: int) -> tuple[list[Any], str | None]:
    start = 0 if cursor is None else next((i for i, x in enumerate(items) if str(x.id) == cursor), len(items))
    end = start + limit
    page = list(items[start:end])
    next_cursor = str(page[-1].id) if end < len(items) and page else None
    return page, next_cursor


class SqlAlchemyDomainRepository(DomainRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, id: UUID) -> Domain | None:
        model = self._session.get(DomainModel, id)
        return domain_from_model(model) if model is not None else None

    async def get_by_host(self, host: str) -> Domain | None:
        normalised = host.strip().lower().rstrip(".")
        stmt = select(DomainModel).where(DomainModel.host == normalised)
        model = self._session.execute(stmt).scalar_one_or_none()
        return domain_from_model(model) if model is not None else None

    async def list(
        self,
        enabled: bool | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Domain], str | None]:
        stmt = select(DomainModel).order_by(DomainModel.id)
        if enabled is not None:
            stmt = stmt.where(DomainModel.enabled == enabled)
        if search is not None:
            stmt = stmt.where(DomainModel.host.ilike(f"%{search}%"))
        models = list(self._session.execute(stmt).scalars().all())
        return _cursor_after(models, cursor, limit)

    async def add(self, entity: Domain) -> None:
        self._session.add(domain_to_model(entity))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                f"domain with host {entity.host.value!r} already exists",
                details={"host": entity.host.value},
            ) from exc

    async def update(self, entity: Domain) -> None:
        model = self._session.get(DomainModel, entity.id)
        if model is None:
            return
        model.host = entity.host.value
        model.display_name = entity.display_name
        model.enabled = entity.enabled
        model.default_crawl_config = entity.default_crawl_config.model_dump()
        model.default_diff_config = entity.default_diff_config.model_dump()
        model.politeness = entity.politeness.model_dump()
        model.default_routing = entity.default_routing.to_dict()
        model.updated_at = entity.updated_at
        self._session.flush()

    async def delete(self, id: UUID) -> None:
        model = self._session.get(DomainModel, id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()


class SqlAlchemyCategoryRepository(CategoryRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, id: UUID) -> Category | None:
        model = self._session.get(CategoryModel, id)
        return category_from_model(model) if model is not None else None

    async def get_by_name(self, domain_id: UUID, name: str) -> Category | None:
        stmt = select(CategoryModel).where(
            CategoryModel.domain_id == domain_id,
            CategoryModel.name == name.strip(),
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return category_from_model(model) if model is not None else None

    async def list_by_domain(
        self,
        domain_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Category], str | None]:
        stmt = select(CategoryModel).where(CategoryModel.domain_id == domain_id).order_by(CategoryModel.id)
        models = list(self._session.execute(stmt).scalars().all())
        return _cursor_after(models, cursor, limit)

    async def list(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Category], str | None]:
        stmt = select(CategoryModel).order_by(CategoryModel.id)
        models = list(self._session.execute(stmt).scalars().all())
        return _cursor_after(models, cursor, limit)

    async def add(self, entity: Category) -> None:
        self._session.add(category_to_model(entity))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                f"category {entity.name!r} already exists in domain",
                details={"name": entity.name},
            ) from exc

    async def update(self, entity: Category) -> None:
        model = self._session.get(CategoryModel, entity.id)
        if model is None:
            return
        model.name = entity.name
        model.description = entity.description
        model.crawl_config = entity.crawl_config.model_dump() if entity.crawl_config else None
        model.diff_config = entity.diff_config.model_dump() if entity.diff_config else None
        model.routing = entity.routing.to_dict() if entity.routing else None
        model.updated_at = entity.updated_at
        self._session.flush()

    async def delete(self, id: UUID) -> None:
        model = self._session.get(CategoryModel, id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()


class SqlAlchemyUrlRepository(UrlRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, id: UUID) -> Url | None:
        model = self._session.get(UrlModel, id)
        return url_from_model(model) if model is not None else None

    async def get_by_address(self, domain_id: UUID, address: str) -> Url | None:
        stmt = select(UrlModel).where(
            UrlModel.domain_id == domain_id,
            UrlModel.address == address,
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return url_from_model(model) if model is not None else None

    async def list(
        self,
        domain_id: UUID | None = None,
        category_id: UUID | None = None,
        status: UrlStatus | None = None,
        enabled: bool | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Url], str | None]:
        stmt = select(UrlModel).order_by(UrlModel.id)
        if domain_id is not None:
            stmt = stmt.where(UrlModel.domain_id == domain_id)
        if category_id is not None:
            stmt = stmt.where(UrlModel.category_id == category_id)
        if status is not None:
            stmt = stmt.where(UrlModel.status == status.value)
        if enabled is not None:
            stmt = stmt.where(UrlModel.enabled == enabled)
        if search is not None:
            stmt = stmt.where(UrlModel.address.ilike(f"%{search}%"))
        models = list(self._session.execute(stmt).scalars().all())
        return _cursor_after(models, cursor, limit)

    async def list_by_category(self, category_id: UUID) -> list[Url]:  # type: ignore[valid-type]
        stmt = select(UrlModel).where(UrlModel.category_id == category_id)
        models = list(self._session.execute(stmt).scalars().all())
        return [url_from_model(m) for m in models]

    async def list_by_domain(self, domain_id: UUID) -> list[Url]:  # type: ignore[valid-type]
        stmt = select(UrlModel).where(UrlModel.domain_id == domain_id)
        models = list(self._session.execute(stmt).scalars().all())
        return [url_from_model(m) for m in models]

    async def list_due(self, *, now: datetime, limit: int = 100) -> list[Url]:  # type: ignore[valid-type]
        stmt = (
            select(UrlModel)
            .where(UrlModel.enabled.is_(True))
            .where(UrlModel.status == "idle")
            .where(UrlModel.next_due_at <= now)
            .order_by(UrlModel.next_due_at, UrlModel.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        models = list(self._session.execute(stmt).scalars().all())
        return [url_from_model(m) for m in models]

    async def add(self, entity: Url) -> None:
        self._session.add(url_to_model(entity))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                f"url with address {entity.address.value!r} already exists in domain",
                details={"address": entity.address.value},
            ) from exc

    async def update(self, entity: Url) -> None:
        model = self._session.get(UrlModel, entity.id)
        if model is None:
            return
        model.category_id = entity.category_id.value if entity.category_id else None
        model.address = entity.address.value
        model.enabled = entity.enabled
        model.crawl_config = entity.crawl_config.model_dump() if entity.crawl_config else None
        model.diff_config = entity.diff_config.model_dump() if entity.diff_config else None
        model.routing = entity.routing.to_dict() if entity.routing else None
        model.interval_seconds = entity.interval.seconds
        model.status = entity.status.value
        model.last_checked_at = entity.last_checked_at
        model.next_due_at = entity.next_due_at
        model.last_hash = entity.last_hash
        model.consecutive_errors = entity.consecutive_errors
        model.locked_by = entity.locked_by
        model.lock_expires_at = entity.lock_expires_at
        model.enqueued_at = entity.enqueued_at
        model.updated_at = entity.updated_at
        self._session.flush()

    async def delete(self, id: UUID) -> None:
        model = self._session.get(UrlModel, id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()


class SqlAlchemyChannelRepository(ChannelRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, id: UUID) -> Channel | None:
        model = self._session.get(ChannelModel, id)
        return channel_from_model(model) if model is not None else None

    async def get_by_name(self, name: str) -> Channel | None:
        stmt = select(ChannelModel).where(ChannelModel.name == name.strip())
        model = self._session.execute(stmt).scalar_one_or_none()
        return channel_from_model(model) if model is not None else None

    async def list(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Channel], str | None]:
        stmt = select(ChannelModel).order_by(ChannelModel.id)
        models = list(self._session.execute(stmt).scalars().all())
        return _cursor_after(models, cursor, limit)

    async def add(self, entity: Channel) -> None:
        self._session.add(channel_to_model(entity))
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError(
                f"channel with name {entity.name!r} already exists",
                details={"name": entity.name},
            ) from exc

    async def update(self, entity: Channel) -> None:
        model = self._session.get(ChannelModel, entity.id)
        if model is None:
            return
        model.name = entity.name
        model.kind = entity.kind.value
        model.apprise_url_encrypted = entity.apprise_url.encode("utf-8")
        model.enabled = entity.enabled
        model.updated_at = entity.updated_at
        self._session.flush()

    async def delete(self, id: UUID) -> None:
        model = self._session.get(ChannelModel, id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()


class SqlAlchemyChannelBindingRepository(ChannelBindingRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, id: UUID) -> ChannelBinding | None:
        model = self._session.get(ChannelBindingModel, id)
        return channel_binding_from_model(model) if model is not None else None

    async def list(
        self,
        scope: str | None = None,
        scope_id: UUID | None = None,
        channel_id: UUID | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[ChannelBinding], str | None]:
        stmt = select(ChannelBindingModel).order_by(ChannelBindingModel.id)
        if scope is not None:
            stmt = stmt.where(ChannelBindingModel.scope == scope)
        if scope_id is not None:
            stmt = stmt.where(ChannelBindingModel.scope_id == scope_id)
        if channel_id is not None:
            stmt = stmt.where(ChannelBindingModel.channel_id == channel_id)
        models = list(self._session.execute(stmt).scalars().all())
        return _cursor_after(models, cursor, limit)

    async def add(self, entity: ChannelBinding) -> None:
        self._session.add(channel_binding_to_model(entity))
        self._session.flush()

    async def update(self, entity: ChannelBinding) -> None:
        model = self._session.get(ChannelBindingModel, entity.id)
        if model is None:
            return
        model.on_change = entity.on_change
        model.on_error = entity.on_error
        model.on_no_change = entity.on_no_change
        self._session.flush()

    async def delete(self, id: UUID) -> None:
        model = self._session.get(ChannelBindingModel, id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()


class SqlAlchemySnapshotRepository(SnapshotRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, id: UUID) -> Snapshot | None:
        model = self._session.get(SnapshotModel, id)
        return snapshot_from_model(model) if model is not None else None

    async def latest_for_url(self, url_id: UUID) -> Snapshot | None:
        stmt = (
            select(SnapshotModel)
            .where(SnapshotModel.url_id == url_id)
            .order_by(SnapshotModel.fetched_at.desc(), SnapshotModel.id.desc())
            .limit(1)
        )
        model = self._session.execute(stmt).scalar_one_or_none()
        return snapshot_from_model(model) if model is not None else None

    async def list_for_url(self, url_id: UUID, *, limit: int = 50) -> list[Snapshot]:
        stmt = (
            select(SnapshotModel)
            .where(SnapshotModel.url_id == url_id)
            .order_by(SnapshotModel.fetched_at.desc(), SnapshotModel.id.desc())
            .limit(limit)
        )
        models = list(self._session.execute(stmt).scalars().all())
        return [snapshot_from_model(m) for m in models]

    async def add(self, entity: Snapshot) -> None:
        self._session.add(snapshot_to_model(entity))
        self._session.flush()

    async def delete(self, id: UUID) -> None:
        model = self._session.get(SnapshotModel, id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()


class SqlAlchemyChangeRepository(ChangeRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, id: UUID) -> Change | None:
        model = self._session.get(ChangeModel, id)
        return change_from_model(model) if model is not None else None

    async def list_for_url(
        self,
        url_id: UUID,
        *,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[Change]:
        stmt = (
            select(ChangeModel)
            .where(ChangeModel.url_id == url_id)
            .order_by(ChangeModel.created_at.desc(), ChangeModel.id.desc())
            .limit(limit)
        )
        if since is not None:
            stmt = stmt.where(ChangeModel.created_at >= since)
        models = list(self._session.execute(stmt).scalars().all())
        return [change_from_model(m) for m in models]

    async def add(self, entity: Change) -> None:
        self._session.add(change_to_model(entity))
        self._session.flush()

    async def update_enrichment_status(self, change_id: UUID, status: str) -> None:
        model = self._session.get(ChangeModel, change_id)
        if model is not None:
            model.enrichment_status = status
            self._session.flush()


class SqlAlchemyUrlCheckStateRepository(UrlCheckStateRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    async def get_for_url(self, url_id: UUID) -> StoredCheckState | None:
        model = self._session.get(UrlCheckStateModel, url_id)
        return url_check_state_from_model(model) if model is not None else None

    async def upsert(self, state: StoredCheckState) -> None:
        model = self._session.get(UrlCheckStateModel, state.url_id)
        if model is None:
            self._session.add(url_check_state_to_model(state))
        else:
            model.raw_md5 = state.raw_md5
            model.filter_config_hash = state.filter_config_hash
            model.last_etag = state.last_etag
            model.last_modified = state.last_modified
            model.zone_hashes = dict(state.zone_hashes)
            model.zone_texts = dict(state.zone_texts)
            model.previous_cleaned_text = state.previous_cleaned_text
            model.last_check_at = state.last_check_at
            model.profile_id = state.profile_id
        self._session.flush()


class SqlAlchemyOutboxRepository(OutboxRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    async def add(
        self,
        *,
        id: UUID,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        event_id: UUID,
        payload: dict[str, Any],
        created_at: datetime,
    ) -> None:
        self._session.add(
            outbox_to_model(
                id=id,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
                event_id=event_id,
                payload=payload,
                created_at=created_at,
            ),
        )
        self._session.flush()

    async def list_unsent(self, *, limit: int = 100) -> list[dict[str, Any]]:
        stmt = select(OutboxModel).where(OutboxModel.sent_at.is_(None)).order_by(OutboxModel.created_at).limit(limit)
        models = list(self._session.execute(stmt).scalars().all())
        return [
            {
                "id": m.id,
                "aggregate_type": m.aggregate_type,
                "aggregate_id": m.aggregate_id,
                "event_type": m.event_type,
                "event_id": m.event_id,
                "payload": dict(m.payload),
                "created_at": m.created_at,
                "attempts": m.attempts,
            }
            for m in models
        ]

    async def mark_sent(self, ids: list[UUID], *, sent_at: datetime) -> None:
        if not ids:
            return
        models = list(
            self._session.execute(
                select(OutboxModel).where(OutboxModel.id.in_(ids)),
            ).scalars(),
        )
        for model in models:
            model.sent_at = sent_at
        self._session.flush()

    async def increment_attempts(self, ids: list[UUID]) -> None:
        if not ids:
            return
        models = list(
            self._session.execute(
                select(OutboxModel).where(OutboxModel.id.in_(ids)),
            ).scalars(),
        )
        for model in models:
            model.attempts += 1
        self._session.flush()


class SqlAlchemyNotificationLogRepository(NotificationLogRepository):
    """Postgres-backed per-channel dedup log.

    The unique key ``(event_id, channel_id)`` is enforced by the
    database; :meth:`record` translates the unique-violation into a
    no-op return value so the use case stays a straight line.
    """

    def __init__(self, session: Session, ids: UuidV7Generator | None = None) -> None:
        self._session = session
        self._ids = ids or UuidV7Generator()

    async def seen(self, *, event_id: UUID, channel_id: UUID) -> bool:
        stmt = select(NotificationLogModel.id).where(
            NotificationLogModel.event_id == event_id,
            NotificationLogModel.channel_id == channel_id,
        )
        return self._session.execute(stmt).first() is not None

    async def record(
        self,
        *,
        event_id: UUID,
        channel_id: UUID,
        status: str,
        error: str | None,
        sent_at: datetime,
    ) -> bool:
        if await self.seen(event_id=event_id, channel_id=channel_id):
            return False
        row = NotificationLogModel(
            id=self._ids.new(),
            event_id=event_id,
            channel_id=channel_id,
            status=status,
            error=error,
            sent_at=sent_at,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            return False
        return True


class SiteProfileRepositoryImpl(SiteProfileRepository):
    """SQLAlchemy-backed :class:`SiteProfileRepository`."""

    def __init__(self, session: Session, ids: UuidV7Generator) -> None:
        self._session = session
        self._ids = ids

    async def get(self, domain: str, url: str) -> SiteProfile | None:
        stmt = (
            select(SiteProfileModel)
            .where(SiteProfileModel.domain == domain)
            .order_by(
                SiteProfileModel.url_pattern.desc(),
                SiteProfileModel.version.desc(),
            )
            .limit(50)
        )
        result = self._session.execute(stmt)
        rows = result.scalars().all()
        if not rows:
            return None

        path = urlparse(url).path or "/"
        best: SiteProfileModel | None = None
        best_specificity = -1
        for row in rows:
            pattern = row.url_pattern
            if _profile_matches(pattern, path):
                specificity = _profile_specificity(pattern)
                if specificity > best_specificity:
                    best_specificity = specificity
                    best = row
        if best is None:
            return None
        return site_profile_from_model(best, now=datetime.min)

    async def upsert(self, profile: SiteProfile) -> None:
        data = site_profile_to_model(profile)
        stmt = select(SiteProfileModel).where(SiteProfileModel.id == profile.id)
        existing = self._session.execute(stmt).scalar_one_or_none()
        if existing is not None:
            for key, value in data.items():
                if key != "id":
                    setattr(existing, key, value)
        else:
            model = SiteProfileModel(**data)
            self._session.add(model)

    async def list_by_domain(self, domain: str) -> list[SiteProfile]:
        stmt = (
            select(SiteProfileModel)
            .where(SiteProfileModel.domain == domain)
            .order_by(SiteProfileModel.url_pattern.desc())
        )
        result = self._session.execute(stmt)
        rows = result.scalars().all()
        return [site_profile_from_model(row, now=datetime.min) for row in rows]


_WILDCARD_RE = re.compile(r"[.+(){}|^$]")
_STAR_RE = re.compile(r"(?P<wild>\*+)")


def _profile_matches(pattern: str, path: str) -> bool:
    if pattern == ".*":
        return True
    escaped = _WILDCARD_RE.sub(r"\\\g<0>", pattern)
    regex_str = _STAR_RE.sub(r"[^/]*", escaped)
    regex_str = f"^{regex_str}$"
    return bool(re.search(regex_str, path))


def _profile_specificity(pattern: str) -> int:
    return len(pattern) - pattern.count("*")


# ---------------------------------------------------------------------------
# AI enrichment repositories (12-ai-enrichment-layer.md)
# ---------------------------------------------------------------------------


class SqlEmbeddingCacheRepository:
    """Implements :class:`lens_application.ports.EmbeddingCacheRepository`.

    Stores embedding vectors in the ``zone_embeddings`` table. A Redis
    hot-cache layer may be placed in front by wrapping an instance of this
    class.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, *, model_id: str, text_hash: str) -> list[float] | None:
        from lens_infrastructure.db.models import ZoneEmbeddingModel

        stmt = select(ZoneEmbeddingModel).where(
            ZoneEmbeddingModel.model_id == model_id,
            ZoneEmbeddingModel.text_hash == text_hash,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return list(row.vector)

    async def put(
        self,
        *,
        model_id: str,
        text_hash: str,
        vector: list[float],
    ) -> None:
        from lens_infrastructure.db.models import ZoneEmbeddingModel

        stmt = select(ZoneEmbeddingModel).where(
            ZoneEmbeddingModel.model_id == model_id,
            ZoneEmbeddingModel.text_hash == text_hash,
        )
        existing = self._session.execute(stmt).scalar_one_or_none()
        if existing is not None:
            existing.vector = vector
        else:
            model = ZoneEmbeddingModel(
                model_id=model_id,
                text_hash=text_hash,
                vector=vector,
            )
            self._session.add(model)


class SqlChangeClassificationRepository:
    """Implements :class:`lens_application.ports.ChangeClassificationRepository`.

    Stores LLM-produced change classifications in the
    ``change_classifications`` table. One classification per change
    (``change_id`` is unique).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, change_id: UUID) -> dict[str, Any] | None:
        from lens_infrastructure.db.models import ChangeClassificationModel

        stmt = select(ChangeClassificationModel).where(
            ChangeClassificationModel.change_id == change_id,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return {
            "change_type": row.change_type,
            "is_meaningful": row.is_meaningful,
            "severity": row.severity,
            "summary": row.summary,
            "extracted_fields": dict(row.extracted_fields),
            "confidence": row.confidence,
            "model_id": row.model_id,
        }

    async def add(
        self,
        change_id: UUID,
        classification: dict[str, Any],
        *,
        model_id: str,
        tokens_used: int,
        llm_latency_ms: int,
    ) -> None:
        from lens_infrastructure.db.models import ChangeClassificationModel

        try:
            model = ChangeClassificationModel(
                change_id=change_id,
                change_type=classification.get("change_type", "other"),
                is_meaningful=bool(classification.get("is_meaningful", False)),
                severity=int(classification.get("severity", 1)),
                summary=str(classification.get("summary", "")),
                extracted_fields=dict(
                    classification.get("extracted_fields", {}),
                ),
                confidence=float(classification.get("confidence", 0.0)),
                model_id=model_id,
                tokens_used=tokens_used,
                llm_latency_ms=llm_latency_ms,
            )
            self._session.add(model)
            self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                f"classification for change {change_id!s} already exists",
            ) from exc


# ---------------------------------------------------------------------------
# Auto-learning repositories (12-ai-enrichment-layer.md §6-§7)
# ---------------------------------------------------------------------------


class SqlChangeLabelRepository:
    """Implements :class:`lens_application.ports.ChangeLabelRepository`.

    Stores labels in the ``change_labels`` table. One label per
    ``(change_id, labeled_by)`` pair (enforced by unique constraint).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    async def get(self, change_id: UUID, labeled_by: str) -> dict[str, Any] | None:
        stmt = select(ChangeLabelModel).where(
            ChangeLabelModel.change_id == change_id,
            ChangeLabelModel.labeled_by == labeled_by,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return {
            "change_id": str(row.change_id),
            "is_change": row.is_change,
            "is_meaningful": row.is_meaningful,
            "change_type": row.change_type,
            "labeled_by": row.labeled_by,
        }

    async def add(self, label: ChangeLabel) -> None:
        try:
            model = ChangeLabelModel(
                change_id=UUID(str(label.change_id)),
                is_change=label.is_change,
                is_meaningful=label.is_meaningful,
                change_type=label.change_type,
                labeled_by=label.labeled_by,
            )
            self._session.add(model)
            self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                f"label for change {label.change_id!s} by {label.labeled_by!r} already exists",
            ) from exc

    async def list_for_domain(
        self,
        domain: str,
        *,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(ChangeLabelModel)
            .join(ChangeModel, ChangeLabelModel.change_id == ChangeModel.id)
            .join(UrlModel, ChangeModel.url_id == UrlModel.id)
            .join(DomainModel, UrlModel.domain_id == DomainModel.id)
            .where(DomainModel.host == domain)
            .limit(limit)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [
            {
                "change_id": str(r.change_id),
                "is_change": r.is_change,
                "is_meaningful": r.is_meaningful,
                "change_type": r.change_type,
                "labeled_by": r.labeled_by,
            }
            for r in rows
        ]

    async def list_for_changes(
        self,
        change_ids: list[UUID],
    ) -> list[dict[str, Any]]:
        stmt = select(ChangeLabelModel).where(
            ChangeLabelModel.change_id.in_(change_ids),
        )
        rows = self._session.execute(stmt).scalars().all()
        return [
            {
                "change_id": str(r.change_id),
                "is_change": r.is_change,
                "is_meaningful": r.is_meaningful,
                "change_type": r.change_type,
                "labeled_by": r.labeled_by,
            }
            for r in rows
        ]
