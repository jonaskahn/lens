"""Application-layer ports (Protocol interfaces).

Repositories are async (they talk to the DB via SQLAlchemy async session).
The Unit of Work guarantees that all repositories built from it share a
single transaction. :class:`ClockPort` and :class:`IdGeneratorPort` are
re-declared here so the application layer can depend on its own
domain-specific ports without reaching into ``lens_common``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from lens_application.pipeline import StoredCheckState
from lens_common.ports import ClockPort as _BaseClock
from lens_common.ports import IdGeneratorPort as _BaseId
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
from lens_domain.value_objects import ChangeLabel

__all__ = [
    "ApiKeyRepository",
    "CategoryRepository",
    "ChangeClassificationRepository",
    "ChangeLabelRepository",
    "ChangeRepository",
    "ChannelBindingRepository",
    "ChannelRepository",
    "ClockPort",
    "ConfigBroadcastPort",
    "DeadLetterRepositoryPort",
    "DomainRepository",
    "EmbeddingCacheRepository",
    "IdGeneratorPort",
    "IdempotencyPort",
    "NotificationLogRepository",
    "OutboxRepository",
    "SettingsRepositoryPort",
    "SnapshotRepository",
    "ThrottlePort",
    "UnitOfWork",
    "UrlCheckStateRepository",
    "UrlRepository",
]


class ClockPort(_BaseClock, Protocol):
    """Application-side alias for the clock port (kept for type safety)."""


class IdGeneratorPort(_BaseId, Protocol):
    """Application-side alias for the id-generator port."""


@runtime_checkable
class DomainRepository(Protocol):
    """Persistence boundary for :class:`lens_domain.entities.Domain`."""

    async def get(self, id: UUID) -> Domain | None: ...
    async def get_by_host(self, host: str) -> Domain | None: ...
    async def list(
        self,
        enabled: bool | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Domain], str | None]: ...
    async def add(self, entity: Domain) -> None: ...
    async def update(self, entity: Domain) -> None: ...
    async def delete(self, id: UUID) -> None: ...


@runtime_checkable
class CategoryRepository(Protocol):
    """Persistence boundary for :class:`lens_domain.entities.Category`."""

    async def get(self, id: UUID) -> Category | None: ...
    async def get_by_name(self, domain_id: UUID, name: str) -> Category | None: ...
    async def list_by_domain(
        self,
        domain_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Category], str | None]: ...
    async def list(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Category], str | None]: ...
    async def add(self, entity: Category) -> None: ...
    async def update(self, entity: Category) -> None: ...
    async def delete(self, id: UUID) -> None: ...


@runtime_checkable
class UrlRepository(Protocol):
    """Persistence boundary for :class:`lens_domain.entities.Url`."""

    async def get(self, id: UUID) -> Url | None: ...
    async def get_by_address(self, domain_id: UUID, address: str) -> Url | None: ...
    async def list(
        self,
        domain_id: UUID | None = None,
        category_id: UUID | None = None,
        status: UrlStatus | None = None,
        enabled: bool | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Url], str | None]: ...
    async def list_by_category(self, category_id: UUID) -> list[Url]: ...  # type: ignore[valid-type]
    async def list_by_domain(self, domain_id: UUID) -> list[Url]: ...  # type: ignore[valid-type]
    async def list_due(self, *, now: datetime, limit: int = 100) -> list[Url]: ...  # type: ignore[valid-type]
    async def add(self, entity: Url) -> None: ...
    async def update(self, entity: Url) -> None: ...
    async def delete(self, id: UUID) -> None: ...


@runtime_checkable
class ChannelRepository(Protocol):
    """Persistence boundary for :class:`lens_domain.entities.Channel`."""

    async def get(self, id: UUID) -> Channel | None: ...
    async def get_by_name(self, name: str) -> Channel | None: ...
    async def list(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Channel], str | None]: ...
    async def add(self, entity: Channel) -> None: ...
    async def update(self, entity: Channel) -> None: ...
    async def delete(self, id: UUID) -> None: ...


@runtime_checkable
class ChannelBindingRepository(Protocol):
    """Persistence boundary for :class:`lens_domain.entities.ChannelBinding`."""

    async def get(self, id: UUID) -> ChannelBinding | None: ...
    async def list(
        self,
        scope: str | None = None,
        scope_id: UUID | None = None,
        channel_id: UUID | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[ChannelBinding], str | None]: ...
    async def add(self, entity: ChannelBinding) -> None: ...
    async def update(self, entity: ChannelBinding) -> None: ...
    async def delete(self, id: UUID) -> None: ...


class UnitOfWork(Protocol):
    """Transactional boundary shared by all repositories built from it.

    Implementations must ensure that all repositories handed out during the
    same UoW see the same in-flight transaction; ``commit`` makes it
    visible, ``rollback`` discards it.
    """

    @property
    def domains(self) -> DomainRepository: ...
    @property
    def categories(self) -> CategoryRepository: ...
    @property
    def urls(self) -> UrlRepository: ...
    @property
    def channels(self) -> ChannelRepository: ...
    @property
    def channel_bindings(self) -> ChannelBindingRepository: ...
    @property
    def snapshots(self) -> SnapshotRepository: ...
    @property
    def changes(self) -> ChangeRepository: ...
    @property
    def outbox(self) -> OutboxRepository: ...
    @property
    def notification_log(self) -> NotificationLogRepository: ...
    @property
    def url_check_states(self) -> UrlCheckStateRepository: ...
    @property
    def change_classifications(self) -> ChangeClassificationRepository: ...
    @property
    def change_labels(self) -> ChangeLabelRepository: ...

    async def __aenter__(self) -> UnitOfWork: ...
    async def __aexit__(self, *exc_info: Any) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
    async def flush(self) -> None: ...
    def new_id(self) -> UUID: ...
    def now(self) -> datetime: ...


@runtime_checkable
class SnapshotRepository(Protocol):
    """Persistence boundary for :class:`lens_domain.entities.Snapshot`."""

    async def get(self, id: UUID) -> Snapshot | None: ...
    async def latest_for_url(self, url_id: UUID) -> Snapshot | None: ...
    async def list_for_url(self, url_id: UUID, *, limit: int = 50) -> list[Snapshot]: ...
    async def add(self, entity: Snapshot) -> None: ...
    async def delete(self, id: UUID) -> None: ...


@runtime_checkable
class ChangeRepository(Protocol):
    """Persistence boundary for :class:`lens_domain.entities.Change`."""

    async def get(self, id: UUID) -> Change | None: ...
    async def list_for_url(
        self,
        url_id: UUID,
        *,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[Change]: ...
    async def add(self, entity: Change) -> None: ...
    async def update_enrichment_status(self, change_id: UUID, status: str) -> None: ...


@runtime_checkable
class UrlCheckStateRepository(Protocol):
    """Persistence boundary for per-URL prior-check state.

    A :class:`StoredCheckState` row is the durable memory of the previous
    check: raw md5, filter-config hash, zone hashes/texts, and the
    previous cleaned text. The use case loads it on entry (to drive
    L0/L1 short-circuits) and writes it on every success/skip so the
    next run has a complete baseline.
    """

    async def get_for_url(self, url_id: UUID) -> StoredCheckState | None: ...
    async def upsert(self, state: StoredCheckState) -> None: ...


@runtime_checkable
class OutboxRepository(Protocol):
    """Persistence boundary for the transactional outbox."""

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
    ) -> None: ...
    async def list_unsent(self, *, limit: int = 100) -> list[dict[str, Any]]: ...
    async def mark_sent(self, ids: list[UUID], *, sent_at: datetime) -> None: ...
    async def increment_attempts(self, ids: list[UUID]) -> None: ...


@runtime_checkable
class NotificationLogRepository(Protocol):
    """Persistence boundary for the per-channel dedup log.

    The unique key ``(event_id, channel_id)`` is enforced by the database
    via the ``notification_log`` table; the repository translates the
    unique-violation into a no-op return value from :meth:`record`.
    """

    async def seen(
        self,
        *,
        event_id: UUID,
        channel_id: UUID,
    ) -> bool: ...

    async def record(
        self,
        *,
        event_id: UUID,
        channel_id: UUID,
        status: str,
        error: str | None,
        sent_at: datetime,
    ) -> bool:
        """Insert a notification-log row; return True if a new row was created."""
        ...


class IdempotencyPort(Protocol):
    async def mark_seen(self, key: str, *, ttl_seconds: int = 86400) -> bool: ...

    async def is_seen(self, key: str) -> bool: ...


class ThrottlePort(Protocol):
    async def acquire(self, host: str) -> bool: ...

    async def release(self, host: str) -> None: ...

    async def delay_seconds(self, host: str) -> float: ...


class SettingsRepositoryPort(Protocol):
    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def list_all(self) -> list[dict[str, Any]]: ...

    async def upsert(self, key: str, value: Any, *, updated_by: str) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def list_audit(self, key: str, *, limit: int = 50) -> list[dict[str, Any]]: ...

    async def get_all_current(self) -> dict[str, Any]: ...


class ConfigBroadcastPort(Protocol):
    async def publish(self, key: str, value: Any, *, version: int) -> None: ...


class DeadLetterRepositoryPort(Protocol):
    async def add(
        self,
        *,
        queue: str,
        message_id: str,
        body: dict[str, Any],
        error: str | None = None,
    ) -> None: ...

    async def list_messages(self, *, queue: str, limit: int = 100) -> list[dict[str, Any]]: ...

    async def replay(self, message_ids: list[str]) -> int: ...

    async def discard(self, message_ids: list[str]) -> int: ...


# ---------------------------------------------------------------------------
# AI enrichment persistence ports (12-ai-enrichment-layer.md §2)
# ---------------------------------------------------------------------------


class EmbeddingCacheRepository(Protocol):
    """Persistence boundary for cached embedding vectors.

    Cache key is ``(model_id, text_hash)``. Redis for hot cache,
    pgvector for durable storage. Implementations may layer Redis in
    front of the database.
    """

    async def get(self, *, model_id: str, text_hash: str) -> list[float] | None: ...

    async def put(self, *, model_id: str, text_hash: str, vector: list[float]) -> None: ...


class ChangeClassificationRepository(Protocol):
    """Persistence boundary for LLM-produced change classifications.

    One classification per change (``change_id`` is unique). The database
    enforces at-most-one via a unique constraint.
    """

    async def get(self, change_id: UUID) -> dict[str, Any] | None: ...

    async def add(
        self,
        change_id: UUID,
        classification: dict[str, Any],
        *,
        model_id: str,
        tokens_used: int,
        llm_latency_ms: int,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Auto-learning persistence ports (12-ai-enrichment-layer.md §6-§7)
# ---------------------------------------------------------------------------


class ChangeLabelRepository(Protocol):
    """Persistence boundary for change labels used in learning and eval.

    Labels can come from humans (``labeled_by='human'``), the LLM
    (``labeled_by='llm'``), or heuristics (``labeled_by='rule'``).
    One label per ``(change_id, labeled_by)`` pair.
    """

    async def get(self, change_id: UUID, labeled_by: str) -> dict[str, Any] | None: ...

    async def add(self, label: ChangeLabel) -> None: ...

    async def list_for_domain(
        self,
        domain: str,
        *,
        limit: int = 500,
    ) -> list[dict[str, Any]]: ...

    async def list_for_changes(
        self,
        change_ids: list[UUID],
    ) -> list[dict[str, Any]]: ...


class ApiKeyRepository(Protocol):
    """Persistence boundary for :class:`lens_api.auth.ApiKey` records.

    The repository is responsible for storing the SHA-256 hash of the
    bearer token (never the plaintext) and for the lookups the API
    needs on every authenticated request. Implementations may also
    expose a list endpoint for the admin UI.
    """

    async def get_by_hash(self, key_hash: str) -> dict[str, Any] | None: ...

    async def list(self, *, limit: int = 100) -> list[dict[str, Any]]: ...

    async def create(
        self,
        *,
        name: str,
        key_hash: str,
        scopes: list[str],  # type: ignore[valid-type]
        enabled: bool = True,
    ) -> dict[str, Any]: ...

    async def disable(self, key_id: str) -> None: ...

    async def delete(self, key_id: str) -> None: ...
