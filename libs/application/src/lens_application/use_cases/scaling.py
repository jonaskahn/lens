from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from lens_application.dto import (
    DeadLetterResult,
    RetentionResult,
    SettingDto,
)
from lens_application.errors import NotFoundError, ValidationFailed
from lens_application.ports import (
    ConfigBroadcastPort,
    DeadLetterRepositoryPort,
    SettingsRepositoryPort,
    UnitOfWork,
)
from lens_application.use_cases._base import UseCase

__all__ = [
    "DeleteSettingUseCase",
    "EnforceRetentionUseCase",
    "GetSettingUseCase",
    "InspectDeadLetterUseCase",
    "ListSettingsUseCase",
    "ReplayDeadLetterUseCase",
    "RetentionDeps",
    "SetSettingUseCase",
    "SweepOrphanBlobsUseCase",
]


@dataclass(slots=True)
class RetentionDeps:
    """External collaborators the retention/orphan-sweep use cases need.

    ``blob_delete`` and ``blob_list_keys`` are sync hooks because the
    current :class:`LocalFileBlobStorage` is sync; an async adapter can
    be wrapped in :func:`asyncio.to_thread` by the composition root.
    """

    blob_delete: Callable[[str], Any]
    blob_list_keys: Callable[[], list[str]]
    orm_session: Any = None


# Internal alias for backwards compatibility with prior imports.
_RetentionDeps = RetentionDeps


class ReplayDeadLetterUseCase(UseCase[list[str], DeadLetterResult]):
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        dlq: DeadLetterRepositoryPort,
    ) -> None:
        super().__init__(uow_factory)
        self._dlq = dlq

    async def run(self, message_ids: list[str], uow: UnitOfWork) -> DeadLetterResult:
        replayed = await self._dlq.replay(message_ids)
        return DeadLetterResult(replayed=replayed)


class InspectDeadLetterUseCase(UseCase[str, list[dict[str, Any]]]):
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        dlq: DeadLetterRepositoryPort,
    ) -> None:
        super().__init__(uow_factory)
        self._dlq = dlq

    async def run(self, queue: str, uow: UnitOfWork) -> list[dict[str, Any]]:
        return await self._dlq.list_messages(queue=queue)


class DiscardDeadLetterUseCase(UseCase[list[str], DeadLetterResult]):
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        dlq: DeadLetterRepositoryPort,
    ) -> None:
        super().__init__(uow_factory)
        self._dlq = dlq

    async def run(self, message_ids: list[str], uow: UnitOfWork) -> DeadLetterResult:
        discarded = await self._dlq.discard(message_ids)
        return DeadLetterResult(discarded=discarded)


class EnforceRetentionUseCase(UseCase[None, RetentionResult]):
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        *,
        max_snapshots: int = 25,
        deps: RetentionDeps | None = None,
    ) -> None:
        super().__init__(uow_factory)
        self._max_snapshots = max_snapshots
        self._deps = deps

    async def run(self, _input: None, uow: UnitOfWork) -> RetentionResult:
        snapshots_evicted = 0
        blobs_deleted = 0
        domains, _ = await uow.domains.list()
        for domain in domains:
            urls: list[Any] = await uow.urls.list_by_domain(domain.id)
            for url in urls:
                snapshots = await uow.snapshots.list_for_url(url.id)
                if len(snapshots) <= self._max_snapshots:
                    continue
                excess = sorted(
                    snapshots,
                    key=lambda s: s.fetched_at,
                )[: len(snapshots) - self._max_snapshots]
                for snapshot in excess:
                    if snapshot.content_ref and self._deps is not None:
                        self._deps.blob_delete(snapshot.content_ref)
                        blobs_deleted += 1
                    await uow.snapshots.delete(snapshot.id)
                    snapshots_evicted += 1
        if snapshots_evicted:
            await uow.flush()
        return RetentionResult(
            snapshots_evicted=snapshots_evicted,
            blobs_deleted=blobs_deleted,
        )


class SweepOrphanBlobsUseCase(UseCase[None, RetentionResult]):
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        deps: RetentionDeps | None = None,
    ) -> None:
        super().__init__(uow_factory)
        self._deps = deps

    async def run(self, _input: None, uow: UnitOfWork) -> RetentionResult:
        if self._deps is None:
            return RetentionResult()
        blob_keys = self._deps.blob_list_keys()
        active_refs: set[str] = set()
        domains, _ = await uow.domains.list()
        for domain in domains:
            urls: list[Any] = await uow.urls.list_by_domain(domain.id)
            for url in urls:
                snapshots = await uow.snapshots.list_for_url(url.id)
                for snap in snapshots:
                    if snap.content_ref:
                        active_refs.add(snap.content_ref)
        orphan_count = 0
        for key in blob_keys:
            if key not in active_refs:
                self._deps.blob_delete(key)
                orphan_count += 1
        return RetentionResult(
            blobs_deleted=orphan_count,
            orphan_blobs_deleted=orphan_count,
        )


class GetSettingUseCase(UseCase[str, SettingDto]):
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        settings_repo: SettingsRepositoryPort,
    ) -> None:
        super().__init__(uow_factory)
        self._settings_repo = settings_repo

    async def run(self, key: str, uow: UnitOfWork) -> SettingDto:
        setting = await self._settings_repo.get(key)
        if setting is None:
            raise NotFoundError(f"setting not found: {key!r}")
        return SettingDto(
            key=key,
            value=setting.get("value"),
            immutable=setting.get("immutable", False),
            role=setting.get("role"),
            updated_at=setting.get("updated_at"),
            updated_by=setting.get("updated_by"),
        )


class SetSettingUseCase(UseCase[dict[str, Any], SettingDto]):
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        settings_repo: SettingsRepositoryPort,
        broadcast: ConfigBroadcastPort | None = None,
    ) -> None:
        super().__init__(uow_factory)
        self._settings_repo = settings_repo
        self._broadcast = broadcast

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> SettingDto:
        key: str = params["key"]
        value: Any = params["value"]
        updated_by: str = params.get("updated_by", "admin")
        existing = await self._settings_repo.get(key)
        if existing and existing.get("immutable"):
            raise ValidationFailed(
                f"setting {key!r} is immutable",
                details={"key": key},
            )
        await self._settings_repo.upsert(key, value, updated_by=updated_by)
        new_version = existing.get("version", 0) + 1 if existing else 1
        if self._broadcast is not None:
            await self._broadcast.publish(key, value, version=new_version)
        return SettingDto(
            key=key,
            value=value,
            immutable=existing.get("immutable", False) if existing else False,
            updated_at=datetime.utcnow(),
            updated_by=updated_by,
        )


class ListSettingsUseCase(UseCase[None, list[SettingDto]]):
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        settings_repo: SettingsRepositoryPort,
    ) -> None:
        super().__init__(uow_factory)
        self._settings_repo = settings_repo

    async def run(self, _input: None, uow: UnitOfWork) -> list[SettingDto]:
        settings = await self._settings_repo.list_all()
        return [
            SettingDto(
                key=s.get("key", ""),
                value=s.get("value"),
                immutable=s.get("immutable", False),
                role=s.get("role"),
                updated_at=s.get("updated_at"),
                updated_by=s.get("updated_by"),
            )
            for s in settings
        ]


class DeleteSettingUseCase(UseCase[str, None]):
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        settings_repo: SettingsRepositoryPort,
    ) -> None:
        super().__init__(uow_factory)
        self._settings_repo = settings_repo

    async def run(self, key: str, uow: UnitOfWork) -> None:
        existing = await self._settings_repo.get(key)
        if existing is None:
            raise NotFoundError(f"setting not found: {key!r}")
        if existing.get("immutable"):
            raise ValidationFailed(
                f"setting {key!r} is immutable",
                details={"key": key},
            )
        await self._settings_repo.delete(key)
