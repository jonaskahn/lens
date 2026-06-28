"""CLI composition: wire the UoW factory + use cases."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from lens_application.pipeline import (
    ChannelSecretProvider,
    NotifierPort,
    TaskPublisherPort,
    TemplateRendererPort,
)
from lens_application.ports import UnitOfWork
from lens_application.use_cases import (
    ClusterTemplatesUseCase,
    CreateCategoryUseCase,
    CreateChannelBindingUseCase,
    CreateChannelUseCase,
    CreateDomainUseCase,
    CreateUrlUseCase,
    DeleteCategoryUseCase,
    DeleteChannelBindingUseCase,
    DeleteChannelUseCase,
    DeleteDomainUseCase,
    DeleteUrlUseCase,
    EvalPipelineUseCase,
    ExportSetupUseCase,
    GetCategoryUseCase,
    GetChangeDiffUseCase,
    GetChannelBindingUseCase,
    GetChannelUseCase,
    GetDomainUseCase,
    GetLatestSnapshotUseCase,
    GetUrlUseCase,
    ImportSetupUseCase,
    LabelChangesUseCase,
    LearnZonesUseCase,
    ListCategoriesUseCase,
    ListChangesUseCase,
    ListChannelBindingsUseCase,
    ListChannelsUseCase,
    ListDomainsUseCase,
    ListUrlsUseCase,
    SendTestNotificationUseCase,
    TriggerCheckUseCase,
    UpdateCategoryUseCase,
    UpdateChannelBindingUseCase,
    UpdateChannelUseCase,
    UpdateDomainUseCase,
    UpdateUrlUseCase,
)

__all__ = ["CliComposition", "build_cli_composition"]


@dataclass(frozen=True, slots=True)
class CliComposition:
    """Holds use case instances wired to a UoW factory."""

    uow_factory: Callable[[], UnitOfWork]
    task_publisher: TaskPublisherPort | None
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
    get_change_diff: GetChangeDiffUseCase
    get_latest_snapshot: GetLatestSnapshotUseCase
    send_test_notification: SendTestNotificationUseCase | None
    learn_zones: LearnZonesUseCase | None = None
    cluster_templates: ClusterTemplatesUseCase | None = None
    eval_pipeline: EvalPipelineUseCase | None = None
    label_changes: LabelChangesUseCase | None = None


class _NoopPublisher:
    async def publish_crawl_task(self, task: Any) -> None:
        raise RuntimeError(
            "no task publisher configured for this composition",
        )


def build_cli_composition(
    uow_factory: Callable[[], UnitOfWork],
    *,
    task_publisher: TaskPublisherPort | None = None,
    renderer: TemplateRendererPort | None = None,
    notifier: NotifierPort | None = None,
    secrets: ChannelSecretProvider | None = None,
    learn_zones: LearnZonesUseCase | None = None,
    cluster_templates: ClusterTemplatesUseCase | None = None,
    eval_pipeline: EvalPipelineUseCase | None = None,
    label_changes: LabelChangesUseCase | None = None,
) -> CliComposition:
    """Build a :class:`CliComposition` rooted at ``uow_factory``."""

    def _uow() -> UnitOfWork:
        return uow_factory()

    if task_publisher is None:
        trigger_publisher: TaskPublisherPort = _NoopPublisher()
    else:
        trigger_publisher = task_publisher

    if renderer is not None and notifier is not None and secrets is not None:
        test_notify: SendTestNotificationUseCase | None = SendTestNotificationUseCase(
            _uow,
            renderer=renderer,
            notifier=notifier,
            secrets=secrets,
        )
    else:
        test_notify = None

    return CliComposition(
        uow_factory=uow_factory,
        task_publisher=task_publisher,
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
        get_change_diff=GetChangeDiffUseCase(_uow),
        get_latest_snapshot=GetLatestSnapshotUseCase(_uow),
        send_test_notification=test_notify,
        learn_zones=learn_zones,
        cluster_templates=cluster_templates,
        eval_pipeline=eval_pipeline,
        label_changes=label_changes,
    )
