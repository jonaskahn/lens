"""In-memory test doubles for application-layer use cases.

The ``InMemoryUnitOfWork`` is a *singleton-style* factory: every UoW instance
shares a single ``InMemoryStore``, so a sequence of use-case calls sees a
consistent state. Tests that need a clean slate call
:func:`reset_in_memory_store` in their setup.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from lens_application.pipeline import StoredCheckState
from lens_application.ports import (
    ApiKeyRepository,
    CategoryRepository,
    ChangeRepository,
    ChannelBindingRepository,
    ChannelRepository,
    DomainRepository,
    NotificationLogRepository,
    OutboxRepository,
    SnapshotRepository,
    UnitOfWork,
    UrlCheckStateRepository,
    UrlRepository,
)
from lens_common.ports import SystemClock, UuidV7Generator
from lens_domain.entities import (
    Category,
    Change,
    Channel,
    ChannelBinding,
    Domain,
    Snapshot,
    Url,
)
from lens_domain.enums import UrlStatus

__all__ = [
    "InMemoryStore",
    "InMemoryUnitOfWork",
    "reset_in_memory_store",
]


def _cursor_of(entity_id: UUID) -> str:
    return str(entity_id)


def _after(items: list, cursor: str | None, limit: int) -> tuple[list, str | None]:
    start = next((i for i, x in enumerate(items) if str(x.id) == cursor), 0) if cursor is not None else 0
    end = start + limit
    page = items[start:end]
    next_cursor = _cursor_of(page[-1].id) if end < len(items) and page else None
    return page, next_cursor


def _matches_search(value: str, search: str | None) -> bool:
    return search is None or search.lower() in value.lower()


class InMemoryStore:
    """Shared, in-memory backing store for repository fakes."""

    def __init__(self) -> None:
        self.domains: list[Domain] = []
        self.categories: list[Category] = []
        self.urls: list[Url] = []
        self.channels: list[Channel] = []
        self.channel_bindings: list[ChannelBinding] = []
        self.snapshots: list[Snapshot] = []
        self.changes: list[Change] = []
        self.outbox: list[dict[str, Any]] = []
        self.notification_log: list[dict[str, Any]] = []
        self.url_check_states: dict[UUID, StoredCheckState] = {}

    def reset(self) -> None:
        self.domains.clear()
        self.categories.clear()
        self.urls.clear()
        self.channels.clear()
        self.channel_bindings.clear()
        self.snapshots.clear()
        self.changes.clear()
        self.outbox.clear()
        self.notification_log.clear()
        self.url_check_states.clear()


_default_store: InMemoryStore = InMemoryStore()


def reset_in_memory_store() -> InMemoryStore:
    """Clear the shared store and return the (empty) instance."""
    _default_store.reset()
    return _default_store


class InMemoryDomainRepository(DomainRepository):
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def get(self, id: UUID) -> Domain | None:
        return next((d for d in self._store.domains if d.id == id), None)

    async def get_by_host(self, host: str) -> Domain | None:
        normalised = host.strip().lower().rstrip(".")
        return next(
            (d for d in self._store.domains if d.host.value == normalised),
            None,
        )

    async def list(
        self,
        enabled: bool | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Domain], str | None]:
        items = [
            d
            for d in self._store.domains
            if (enabled is None or d.enabled == enabled) and _matches_search(d.host.value, search)
        ]
        items.sort(key=lambda d: str(d.id))
        return _after(items, cursor, limit)

    async def add(self, entity: Domain) -> None:
        self._store.domains.append(entity)

    async def update(self, entity: Domain) -> None:
        for i, item in enumerate(self._store.domains):
            if item.id == entity.id:
                self._store.domains[i] = entity
                return

    async def delete(self, id: UUID) -> None:
        self._store.domains = [d for d in self._store.domains if d.id != id]


class InMemoryCategoryRepository(CategoryRepository):
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def get(self, id: UUID) -> Category | None:
        return next((c for c in self._store.categories if c.id == id), None)

    async def get_by_name(self, domain_id: UUID, name: str) -> Category | None:
        normalised = name.strip()
        return next(
            (c for c in self._store.categories if c.domain_id.value == domain_id and c.name == normalised),
            None,
        )

    async def list_by_domain(
        self,
        domain_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Category], str | None]:
        items = [c for c in self._store.categories if c.domain_id.value == domain_id]
        items.sort(key=lambda c: str(c.id))
        return _after(items, cursor, limit)

    async def list(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Category], str | None]:
        items = sorted(self._store.categories, key=lambda c: str(c.id))
        return _after(items, cursor, limit)

    async def add(self, entity: Category) -> None:
        self._store.categories.append(entity)

    async def update(self, entity: Category) -> None:
        for i, item in enumerate(self._store.categories):
            if item.id == entity.id:
                self._store.categories[i] = entity
                return

    async def delete(self, id: UUID) -> None:
        self._store.categories = [c for c in self._store.categories if c.id != id]


class InMemoryUrlRepository(UrlRepository):
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def get(self, id: UUID) -> Url | None:
        return next((u for u in self._store.urls if u.id == id), None)

    async def get_by_address(self, domain_id: UUID, address: str) -> Url | None:
        return next(
            (u for u in self._store.urls if u.domain_id.value == domain_id and u.address.value == address),
            None,
        )

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
        items = [
            u
            for u in self._store.urls
            if (domain_id is None or u.domain_id.value == domain_id)
            and (category_id is None or (u.category_id and u.category_id.value == category_id))
            and (status is None or u.status == status)
            and (enabled is None or u.enabled == enabled)
            and _matches_search(u.address.value, search)
        ]
        items.sort(key=lambda u: str(u.id))
        return _after(items, cursor, limit)

    async def list_by_category(self, category_id: UUID) -> list[Url]:
        return [u for u in self._store.urls if u.category_id and u.category_id.value == category_id]

    async def list_by_domain(self, domain_id: UUID) -> list[Url]:
        return [u for u in self._store.urls if u.domain_id.value == domain_id]

    async def list_due(self, *, now: datetime, limit: int = 100) -> list[Url]:
        items = [u for u in self._store.urls if u.enabled and u.status == UrlStatus.IDLE and u.next_due_at <= now]
        items.sort(key=lambda u: (u.next_due_at, str(u.id)))
        return items[:limit]

    async def add(self, entity: Url) -> None:
        self._store.urls.append(entity)

    async def update(self, entity: Url) -> None:
        for i, item in enumerate(self._store.urls):
            if item.id == entity.id:
                self._store.urls[i] = entity
                return

    async def delete(self, id: UUID) -> None:
        self._store.urls = [u for u in self._store.urls if u.id != id]


class InMemoryChannelRepository(ChannelRepository):
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def get(self, id: UUID) -> Channel | None:
        return next((c for c in self._store.channels if c.id == id), None)

    async def get_by_name(self, name: str) -> Channel | None:
        return next(
            (c for c in self._store.channels if c.name == name.strip()),
            None,
        )

    async def list(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Channel], str | None]:
        items = sorted(self._store.channels, key=lambda c: str(c.id))
        return _after(items, cursor, limit)

    async def add(self, entity: Channel) -> None:
        self._store.channels.append(entity)

    async def update(self, entity: Channel) -> None:
        for i, item in enumerate(self._store.channels):
            if item.id == entity.id:
                self._store.channels[i] = entity
                return

    async def delete(self, id: UUID) -> None:
        self._store.channels = [c for c in self._store.channels if c.id != id]


class InMemoryChannelBindingRepository(ChannelBindingRepository):
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def get(self, id: UUID) -> ChannelBinding | None:
        return next((b for b in self._store.channel_bindings if b.id == id), None)

    async def list(
        self,
        scope: str | None = None,
        scope_id: UUID | None = None,
        channel_id: UUID | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[ChannelBinding], str | None]:
        items = [
            b
            for b in self._store.channel_bindings
            if (scope is None or b.scope.value == scope)
            and (scope_id is None or b.scope_id == scope_id)
            and (channel_id is None or b.channel_id == channel_id)
        ]
        items.sort(key=lambda b: str(b.id))
        return _after(items, cursor, limit)

    async def add(self, entity: ChannelBinding) -> None:
        self._store.channel_bindings.append(entity)

    async def update(self, entity: ChannelBinding) -> None:
        for i, item in enumerate(self._store.channel_bindings):
            if item.id == entity.id:
                self._store.channel_bindings[i] = entity
                return

    async def delete(self, id: UUID) -> None:
        self._store.channel_bindings = [b for b in self._store.channel_bindings if b.id != id]


class InMemorySnapshotRepository(SnapshotRepository):
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def get(self, id: UUID) -> Snapshot | None:
        return next((s for s in self._store.snapshots if s.id == id), None)

    async def latest_for_url(self, url_id: UUID) -> Snapshot | None:
        candidates = [s for s in self._store.snapshots if s.url_id.value == url_id]
        if not candidates:
            return None
        candidates.sort(key=lambda s: (s.fetched_at, str(s.id)), reverse=True)
        return candidates[0]

    async def list_for_url(self, url_id: UUID, *, limit: int = 50) -> list[Snapshot]:
        candidates = [s for s in self._store.snapshots if s.url_id.value == url_id]
        candidates.sort(key=lambda s: (s.fetched_at, str(s.id)), reverse=True)
        return candidates[:limit]

    async def add(self, entity: Snapshot) -> None:
        self._store.snapshots.append(entity)

    async def delete(self, id: UUID) -> None:
        self._store.snapshots = [s for s in self._store.snapshots if s.id != id]


class InMemoryChangeRepository(ChangeRepository):
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def get(self, id: UUID) -> Change | None:
        return next((c for c in self._store.changes if c.id == id), None)

    async def list_for_url(
        self,
        url_id: UUID,
        *,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[Change]:
        items = [c for c in self._store.changes if c.url_id.value == url_id]
        if since is not None:
            items = [c for c in items if c.created_at >= since]
        items.sort(key=lambda c: (c.created_at, str(c.id)), reverse=True)
        return items[:limit]

    async def add(self, entity: Change) -> None:
        self._store.changes.append(entity)


class InMemoryOutboxRepository(OutboxRepository):
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

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
        self._store.outbox.append(
            {
                "id": id,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_type": event_type,
                "event_id": event_id,
                "payload": payload,
                "created_at": created_at,
                "sent_at": None,
                "attempts": 0,
            },
        )

    async def list_unsent(self, *, limit: int = 100) -> list[dict[str, Any]]:
        items = [o for o in self._store.outbox if o["sent_at"] is None]
        items.sort(key=lambda o: o["created_at"])
        return items[:limit]

    async def mark_sent(self, ids: list[UUID], *, sent_at: datetime) -> None:
        ids_set = set(ids)
        for row in self._store.outbox:
            if row["id"] in ids_set:
                row["sent_at"] = sent_at

    async def increment_attempts(self, ids: list[UUID]) -> None:
        ids_set = set(ids)
        for row in self._store.outbox:
            if row["id"] in ids_set:
                row["attempts"] += 1


class InMemoryNotificationLogRepository(NotificationLogRepository):
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def seen(self, *, event_id: UUID, channel_id: UUID) -> bool:
        return any(
            row["event_id"] == event_id and row["channel_id"] == channel_id for row in self._store.notification_log
        )

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
        self._store.notification_log.append(
            {
                "event_id": event_id,
                "channel_id": channel_id,
                "status": status,
                "error": error,
                "sent_at": sent_at,
            },
        )
        return True


class InMemoryUrlCheckStateRepository(UrlCheckStateRepository):
    def __init__(self, store: InMemoryStore) -> None:
        self._store = store

    async def get_for_url(self, url_id: UUID) -> StoredCheckState | None:
        return self._store.url_check_states.get(url_id)

    async def upsert(self, state: StoredCheckState) -> None:
        self._store.url_check_states[state.url_id] = state


class InMemoryUnitOfWork(UnitOfWork):
    """A trivial in-memory UoW; all instances share the same backing store."""

    def __init__(self, store: InMemoryStore | None = None) -> None:
        store = store or _default_store
        self._domains = InMemoryDomainRepository(store)
        self._categories = InMemoryCategoryRepository(store)
        self._urls = InMemoryUrlRepository(store)
        self._channels = InMemoryChannelRepository(store)
        self._channel_bindings = InMemoryChannelBindingRepository(store)
        self._snapshots = InMemorySnapshotRepository(store)
        self._changes = InMemoryChangeRepository(store)
        self._outbox = InMemoryOutboxRepository(store)
        self._notification_log = InMemoryNotificationLogRepository(store)
        self._url_check_states = InMemoryUrlCheckStateRepository(store)
        self._clock = SystemClock()
        self._ids = UuidV7Generator()
        self._committed = False
        self._store = store

    @property
    def domains(self) -> DomainRepository:
        return self._domains

    @property
    def categories(self) -> CategoryRepository:
        return self._categories

    @property
    def urls(self) -> UrlRepository:
        return self._urls

    @property
    def channels(self) -> ChannelRepository:
        return self._channels

    @property
    def channel_bindings(self) -> ChannelBindingRepository:
        return self._channel_bindings

    @property
    def snapshots(self) -> SnapshotRepository:
        return self._snapshots

    @property
    def changes(self) -> ChangeRepository:
        return self._changes

    @property
    def outbox(self) -> OutboxRepository:
        return self._outbox

    @property
    def notification_log(self) -> NotificationLogRepository:
        return self._notification_log

    @property
    def url_check_states(self) -> UrlCheckStateRepository:
        return self._url_check_states

    async def __aenter__(self) -> UnitOfWork:
        return self

    async def __aexit__(self, *_exc_info: Any) -> None:
        if not self._committed and _exc_info[0] is not None:
            await self.rollback()

    async def commit(self) -> None:
        self._committed = True

    async def rollback(self) -> None:
        self._committed = False

    async def flush(self) -> None:
        return None

    def new_id(self) -> UUID:
        return self._ids.new()

    def now(self) -> datetime:
        return self._clock.now()


class InMemoryApiKeyRepository(ApiKeyRepository):
    """In-memory implementation of the :class:`ApiKeyRepository` port."""

    def __init__(self) -> None:
        self._by_hash: dict[str, dict[str, Any]] = {}
        self._by_id: dict[str, dict[str, Any]] = {}

    async def get_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        return self._by_hash.get(key_hash)

    async def list(self, *, limit: int = 100) -> list[dict[str, Any]]:
        items = sorted(self._by_id.values(), key=lambda r: str(r["id"]))
        return items[:limit]

    async def create(
        self,
        *,
        name: str,
        key_hash: str,
        scopes: list[str],
        enabled: bool = True,
    ) -> dict[str, Any]:
        from datetime import UTC, datetime

        record = {
            "id": UuidV7Generator().new(),
            "name": name,
            "scopes": list(scopes),
            "enabled": enabled,
            "created_at": datetime.now(UTC),
        }
        self._by_hash[key_hash] = record
        self._by_id[str(record["id"])] = record
        return record

    async def disable(self, key_id: str) -> None:
        record = self._by_id.get(key_id)
        if record is not None:
            record["enabled"] = False

    async def delete(self, key_id: str) -> None:
        record = self._by_id.pop(key_id, None)
        if record is None:
            return
        for hash_value, candidate in list(self._by_hash.items()):
            if candidate is record:
                self._by_hash.pop(hash_value, None)
                break


def make_uow_factory() -> InMemoryUnitOfWork:
    """Return a fresh UoW that shares the default backing store."""
    return InMemoryUnitOfWork()
