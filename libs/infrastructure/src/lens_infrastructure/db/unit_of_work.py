"""SQLAlchemy-backed Unit of Work.

The UoW opens a sync session per use case, runs the use case logic on it,
and commits (or rolls back on exception). All repositories exposed by the
UoW share the same session / transaction.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from lens_application.ports import (
    CategoryRepository,
    ChangeClassificationRepository,
    ChangeLabelRepository,
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
from lens_infrastructure.db.repositories import (
    SqlAlchemyCategoryRepository,
    SqlAlchemyChangeRepository,
    SqlAlchemyChannelBindingRepository,
    SqlAlchemyChannelRepository,
    SqlAlchemyDomainRepository,
    SqlAlchemyNotificationLogRepository,
    SqlAlchemyOutboxRepository,
    SqlAlchemySnapshotRepository,
    SqlAlchemyUrlCheckStateRepository,
    SqlAlchemyUrlRepository,
    SqlChangeClassificationRepository,
    SqlChangeLabelRepository,
)

__all__ = [
    "SqlAlchemyUnitOfWork",
    "sqlalchemy_uow_factory",
]


class SqlAlchemyUnitOfWork(UnitOfWork):
    """A single-transaction UoW that hands repositories the same :class:`Session`."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._clock = SystemClock()
        self._ids = UuidV7Generator()
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._session is None:
            return
        try:
            if exc_info[0] is not None and not self._committed:
                self._session.rollback()
        finally:
            self._session.close()
            self._session = None

    @property
    def _active(self) -> Session:
        if self._session is None:
            raise RuntimeError("UnitOfWork used outside of 'async with'")
        return self._session

    @property
    def domains(self) -> DomainRepository:
        return SqlAlchemyDomainRepository(self._active)

    @property
    def categories(self) -> CategoryRepository:
        return SqlAlchemyCategoryRepository(self._active)

    @property
    def urls(self) -> UrlRepository:
        return SqlAlchemyUrlRepository(self._active)

    @property
    def channels(self) -> ChannelRepository:
        return SqlAlchemyChannelRepository(self._active)

    @property
    def channel_bindings(self) -> ChannelBindingRepository:
        return SqlAlchemyChannelBindingRepository(self._active)

    @property
    def snapshots(self) -> SnapshotRepository:
        return SqlAlchemySnapshotRepository(self._active)

    @property
    def changes(self) -> ChangeRepository:
        return SqlAlchemyChangeRepository(self._active)

    @property
    def outbox(self) -> OutboxRepository:
        return SqlAlchemyOutboxRepository(self._active)

    @property
    def notification_log(self) -> NotificationLogRepository:
        return SqlAlchemyNotificationLogRepository(self._active, ids=self._ids)

    @property
    def url_check_states(self) -> UrlCheckStateRepository:
        return SqlAlchemyUrlCheckStateRepository(self._active)

    @property
    def change_classifications(self) -> ChangeClassificationRepository:
        return SqlChangeClassificationRepository(self._active)

    @property
    def change_labels(self) -> ChangeLabelRepository:
        return SqlChangeLabelRepository(self._active)

    async def commit(self) -> None:
        if self._session is None:
            return
        self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        if self._session is None:
            return
        self._session.rollback()
        self._committed = False

    async def flush(self) -> None:
        if self._session is None:
            return
        self._session.flush()

    def new_id(self) -> UUID:
        return self._ids.new()

    def now(self) -> datetime:
        return self._clock.now()


def sqlalchemy_uow_factory(engine: Engine) -> Callable[[], SqlAlchemyUnitOfWork]:
    """Build a factory that returns a fresh UoW over ``engine``.

    Returns a zero-arg callable suitable for injection into use cases
    that expect ``Callable[[], UnitOfWork]``.
    """
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def _factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(factory)

    return _factory
