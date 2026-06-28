"""Composition root: wire the UoW factory + use cases for the API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lens_application.pipeline import (
    BlobStoragePort,
    TaskPublisherPort,
)
from lens_application.ports import (
    ApiKeyRepository,
    ChangeClassificationRepository,
    ConfigBroadcastPort,
    DeadLetterRepositoryPort,
    SettingsRepositoryPort,
    UnitOfWork,
)
from lens_application.use_cases import (
    CreateApiKeyUseCase,
    CreateCategoryUseCase,
    CreateChannelBindingUseCase,
    CreateChannelUseCase,
    CreateDomainUseCase,
    CreateUrlUseCase,
    DeleteApiKeyUseCase,
    DeleteCategoryUseCase,
    DeleteChannelBindingUseCase,
    DeleteChannelUseCase,
    DeleteDomainUseCase,
    DeleteSettingUseCase,
    DeleteUrlUseCase,
    DiscardDeadLetterUseCase,
    EnforceRetentionUseCase,
    ExportSetupUseCase,
    GetCategoryUseCase,
    GetChangeDiffBlobUseCase,
    GetChangeDiffUseCase,
    GetChangeUseCase,
    GetChannelBindingUseCase,
    GetChannelUseCase,
    GetDomainUseCase,
    GetLatestSnapshotUseCase,
    GetSettingUseCase,
    GetSnapshotUseCase,
    GetUrlUseCase,
    ImportSetupUseCase,
    InspectDeadLetterUseCase,
    ListApiKeysUseCase,
    ListCategoriesUseCase,
    ListChangesUseCase,
    ListChannelBindingsUseCase,
    ListChannelsUseCase,
    ListDomainsUseCase,
    ListSettingsUseCase,
    ListSnapshotsUseCase,
    ListUrlsUseCase,
    ReplayDeadLetterUseCase,
    SetSettingUseCase,
    SweepOrphanBlobsUseCase,
    TriggerCheckUseCase,
    UpdateCategoryUseCase,
    UpdateChannelBindingUseCase,
    UpdateChannelUseCase,
    UpdateDomainUseCase,
    UpdateUrlUseCase,
)
from lens_application.use_cases.scaling import RetentionDeps
from lens_common.health import HealthCheck

__all__ = ["Composition", "build_composition"]


@dataclass(frozen=True, slots=True)
class Composition:
    uow_factory: Callable[[], UnitOfWork]
    task_publisher: TaskPublisherPort | None
    health_check: HealthCheck | None
    config_broadcast: ConfigBroadcastPort | None
    create_domain: CreateDomainUseCase
    get_domain: GetDomainUseCase
    list_domains: ListDomainsUseCase
    update_domain: UpdateDomainUseCase
    delete_domain: DeleteDomainUseCase
    create_category: CreateCategoryUseCase
    get_category: GetCategoryUseCase
    list_categories: ListCategoriesUseCase
    update_category: UpdateCategoryUseCase
    delete_category: DeleteCategoryUseCase
    create_url: CreateUrlUseCase
    get_url: GetUrlUseCase
    list_urls: ListUrlsUseCase
    update_url: UpdateUrlUseCase
    delete_url: DeleteUrlUseCase
    create_channel: CreateChannelUseCase
    get_channel: GetChannelUseCase
    list_channels: ListChannelsUseCase
    update_channel: UpdateChannelUseCase
    delete_channel: DeleteChannelUseCase
    create_channel_binding: CreateChannelBindingUseCase
    get_channel_binding: GetChannelBindingUseCase
    list_channel_bindings: ListChannelBindingsUseCase
    update_channel_binding: UpdateChannelBindingUseCase
    delete_channel_binding: DeleteChannelBindingUseCase
    import_setup: ImportSetupUseCase
    export_setup: ExportSetupUseCase
    trigger_check: TriggerCheckUseCase
    list_changes: ListChangesUseCase
    get_change: GetChangeUseCase
    get_change_diff: GetChangeDiffUseCase
    get_change_diff_blob: GetChangeDiffBlobUseCase | None
    get_snapshot: GetSnapshotUseCase
    get_latest_snapshot: GetLatestSnapshotUseCase
    list_snapshots: ListSnapshotsUseCase
    replay_dlq: ReplayDeadLetterUseCase | None
    inspect_dlq: InspectDeadLetterUseCase | None
    discard_dlq: DiscardDeadLetterUseCase | None
    enforce_retention: EnforceRetentionUseCase | None
    sweep_orphans: SweepOrphanBlobsUseCase | None
    get_setting: GetSettingUseCase | None
    set_setting: SetSettingUseCase | None
    list_settings: ListSettingsUseCase | None
    delete_setting: DeleteSettingUseCase | None
    classification_repo: ChangeClassificationRepository | None
    api_key_repo: ApiKeyRepository | None
    create_api_key: CreateApiKeyUseCase | None
    list_api_keys: ListApiKeysUseCase | None
    delete_api_key: DeleteApiKeyUseCase | None


def build_composition(
    uow_factory: Callable[[], UnitOfWork],
    *,
    task_publisher: TaskPublisherPort | None = None,
    dlq: DeadLetterRepositoryPort | None = None,
    settings_repo: SettingsRepositoryPort | None = None,
    config_broadcast: ConfigBroadcastPort | None = None,
    classification_repo: ChangeClassificationRepository | None = None,
    blob_storage: BlobStoragePort | None = None,
    retention_deps: RetentionDeps | None = None,
    max_snapshots: int = 25,
    api_key_repo: ApiKeyRepository | None = None,
) -> Composition:
    """Build a :class:`Composition` rooted at ``uow_factory``."""

    def _uow() -> UnitOfWork:
        return uow_factory()

    if task_publisher is None:

        class _NoopPublisher:
            async def publish_crawl_task(self, task: Any) -> None:
                raise RuntimeError(
                    "no task publisher configured for this composition",
                )

        trigger_publisher: TaskPublisherPort = _NoopPublisher()
    else:
        trigger_publisher = task_publisher

    return Composition(
        uow_factory=uow_factory,
        task_publisher=task_publisher,
        health_check=HealthCheck(),
        config_broadcast=config_broadcast,
        create_domain=CreateDomainUseCase(_uow),
        get_domain=GetDomainUseCase(_uow),
        list_domains=ListDomainsUseCase(_uow),
        update_domain=UpdateDomainUseCase(_uow),
        delete_domain=DeleteDomainUseCase(_uow),
        create_category=CreateCategoryUseCase(_uow),
        get_category=GetCategoryUseCase(_uow),
        list_categories=ListCategoriesUseCase(_uow),
        update_category=UpdateCategoryUseCase(_uow),
        delete_category=DeleteCategoryUseCase(_uow),
        create_url=CreateUrlUseCase(_uow),
        get_url=GetUrlUseCase(_uow),
        list_urls=ListUrlsUseCase(_uow),
        update_url=UpdateUrlUseCase(_uow),
        delete_url=DeleteUrlUseCase(_uow),
        create_channel=CreateChannelUseCase(_uow),
        get_channel=GetChannelUseCase(_uow),
        list_channels=ListChannelsUseCase(_uow),
        update_channel=UpdateChannelUseCase(_uow),
        delete_channel=DeleteChannelUseCase(_uow),
        create_channel_binding=CreateChannelBindingUseCase(_uow),
        get_channel_binding=GetChannelBindingUseCase(_uow),
        list_channel_bindings=ListChannelBindingsUseCase(_uow),
        update_channel_binding=UpdateChannelBindingUseCase(_uow),
        delete_channel_binding=DeleteChannelBindingUseCase(_uow),
        import_setup=ImportSetupUseCase(_uow),
        export_setup=ExportSetupUseCase(_uow),
        trigger_check=TriggerCheckUseCase(_uow, trigger_publisher),
        list_changes=ListChangesUseCase(_uow),
        get_change=GetChangeUseCase(_uow),
        get_change_diff=GetChangeDiffUseCase(_uow),
        get_change_diff_blob=(GetChangeDiffBlobUseCase(blob_storage) if blob_storage is not None else None),
        get_snapshot=GetSnapshotUseCase(_uow),
        get_latest_snapshot=GetLatestSnapshotUseCase(_uow),
        list_snapshots=ListSnapshotsUseCase(_uow),
        replay_dlq=ReplayDeadLetterUseCase(_uow, dlq) if dlq else None,
        inspect_dlq=InspectDeadLetterUseCase(_uow, dlq) if dlq else None,
        discard_dlq=DiscardDeadLetterUseCase(_uow, dlq) if dlq else None,
        enforce_retention=EnforceRetentionUseCase(
            _uow,
            max_snapshots=max_snapshots,
            deps=retention_deps,
        ),
        sweep_orphans=SweepOrphanBlobsUseCase(_uow, deps=retention_deps),
        get_setting=GetSettingUseCase(_uow, settings_repo) if settings_repo else None,
        set_setting=SetSettingUseCase(_uow, settings_repo, config_broadcast) if settings_repo else None,
        list_settings=ListSettingsUseCase(_uow, settings_repo) if settings_repo else None,
        delete_setting=DeleteSettingUseCase(_uow, settings_repo) if settings_repo else None,
        classification_repo=classification_repo,
        api_key_repo=api_key_repo,
        create_api_key=CreateApiKeyUseCase(_uow, api_key_repo) if api_key_repo else None,
        list_api_keys=ListApiKeysUseCase(_uow, api_key_repo) if api_key_repo else None,
        delete_api_key=DeleteApiKeyUseCase(_uow, api_key_repo) if api_key_repo else None,
    )
