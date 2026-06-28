"""Tests for the notification use cases.

These tests build a real domain graph (domain, category, url, channels,
bindings) via the in-memory UoW, then exercise:

* :class:`PublishOutboxUseCase` - drains unsent outbox rows.
* :class:`HandleChangeEventUseCase` - dedups + routes + renders + sends.
* :class:`HandleErrorEventUseCase` - same path, ``on_error`` trigger.
* :class:`HandleStaleEventUseCase` - same path, ``on_no_change`` trigger.
* :class:`SendTestNotificationUseCase` - sends one sample message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from tests._fakes import InMemoryStore, InMemoryUnitOfWork, reset_in_memory_store

from lens_application.dto import EventEnvelope
from lens_application.errors import NotFoundError
from lens_application.pipeline import (
    NotifierPort,
    RenderedMessage,
    SendResult,
    TemplateRendererPort,
)
from lens_application.use_cases import (
    CreateCategoryUseCase,
    CreateChannelBindingUseCase,
    CreateChannelUseCase,
    CreateDomainUseCase,
    CreateUrlUseCase,
    HandleChangeEventUseCase,
    HandleErrorEventUseCase,
    HandleStaleEventUseCase,
    SendTestNotificationUseCase,
)
from lens_application.use_cases.notifications import (
    PublishOutboxUseCase as _PublishOutbox,
)
from lens_domain.services import NotificationRouter

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test doubles for the notification ports
# ---------------------------------------------------------------------------


@dataclass
class _RecordingNotifier:
    """Captures every :meth:`send` invocation for assertion."""

    sent: list[dict[str, Any]] = field(default_factory=list)
    fail_for: set[UUID] = field(default_factory=set)

    async def send(
        self,
        *,
        channel_kind: str,
        apprise_url: str,
        message: RenderedMessage,
    ) -> SendResult:
        self.sent.append(
            {
                "channel_kind": channel_kind,
                "apprise_url": apprise_url,
                "subject": message.subject,
                "body": message.body,
                "template": message.template,
            },
        )
        # Decide success/failure from the apprise_url (test encodes the channel id)
        for channel_id in self.fail_for:
            marker = f"://{channel_id}/"
            if marker in apprise_url:
                return SendResult(success=False, error="simulated failure")
        return SendResult(success=True)


class _StaticRenderer:
    """Returns a deterministic rendered message."""

    template: str = "change.txt"

    def render(
        self,
        *,
        template_name: str,
        context: dict[str, Any],
    ) -> RenderedMessage:
        return RenderedMessage(
            subject=f"[lens] {context['app_name']} {template_name}",
            body=f"template={template_name} domain={context['domain']} url={context['url']}",
            template=template_name,
        )


@dataclass
class _StaticSecrets:
    """Maps a channel id to a deterministic Apprise URL."""

    def apprise_url_for(self, channel: Any) -> str:
        return f"json://{channel.id}/notify"


@dataclass
class _MemoryBlob:
    """An in-memory BlobStoragePort for tests."""

    store: dict[str, bytes] = field(default_factory=dict)

    async def put(self, key: str, data: bytes) -> str:
        self.store[key] = data
        return key

    async def get(self, key: str) -> bytes:
        return self.store[key]

    async def delete(self, key: str) -> None:
        self.store.pop(key, None)


@dataclass
class _CapturingPublisher:
    """Captures every broker publish for assertion."""

    published: list[dict[str, Any]] = field(default_factory=list)
    fail_first: int = 0

    async def publish(
        self,
        *,
        exchange: str,
        routing_key: str,
        body: dict[str, Any],
    ) -> None:
        if self.fail_first > 0:
            self.fail_first -= 1
            raise RuntimeError("simulated publish failure")
        self.published.append(
            {"exchange": exchange, "routing_key": routing_key, "body": body},
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uow_factory_with_store(store: InMemoryStore) -> callable:  # type: ignore[type-arg]
    def _factory() -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(store=store)

    return _factory


async def _seed_world(
    store: InMemoryStore,
    *,
    on_change: bool = True,
    on_error: bool = False,
    on_no_change: bool = False,
) -> dict[str, Any]:
    uow_factory = _uow_factory_with_store(store)
    domain = await CreateDomainUseCase(uow_factory).execute(
        type(
            "Input",
            (),
            {
                "host": "shop.example.com",
                "display_name": None,
                "enabled": True,
                "default_crawl_config": None,
                "default_diff_config": None,
                "politeness": None,
                "default_routing": None,
            },
        )(),
    )
    category = await CreateCategoryUseCase(uow_factory).execute(
        type(
            "Input",
            (),
            {
                "domain_id": domain.id,
                "name": "products",
                "description": None,
                "crawl_config": None,
                "diff_config": None,
                "routing": None,
            },
        )(),
    )
    url = await CreateUrlUseCase(uow_factory).execute(
        type(
            "Input",
            (),
            {
                "domain_id": domain.id,
                "address": "https://shop.example.com/p/1",
                "category_id": category.id,
                "enabled": True,
                "interval_seconds": 600,
                "crawl_config": None,
                "diff_config": None,
                "routing": None,
            },
        )(),
    )
    channel = await CreateChannelUseCase(uow_factory).execute(
        type(
            "Input",
            (),
            {
                "name": "ops",
                "kind": "webhook",
                "apprise_url": "json://initial/notify",
                "enabled": True,
            },
        )(),
    )
    await CreateChannelBindingUseCase(uow_factory).execute(
        type(
            "Input",
            (),
            {
                "channel_id": channel.id,
                "scope": "global",
                "scope_id": None,
                "on_change": on_change,
                "on_error": on_error,
                "on_no_change": on_no_change,
            },
        )(),
    )
    return {
        "domain": domain,
        "category": category,
        "url": url,
        "channel": channel,
    }


def _event_envelope(
    world: dict[str, Any],
    *,
    type: str = "UrlChangeDetected",
    change_id: UUID | None = None,
    error: str | None = None,
    consecutive_errors: int | None = None,
) -> EventEnvelope:
    return EventEnvelope(
        message_id=uuid4(),
        type=type,
        occurred_at=datetime(2026, 1, 1, 12, 0, 0),
        url_id=world["url"].id,
        domain_id=world["domain"].id,
        category_id=world["category"].id,
        change_id=change_id,
        significant=True,
        error=error,
        consecutive_errors=consecutive_errors,
    )


def _build_handler_components(
    store: InMemoryStore,
    *,
    notifier: NotifierPort,
    renderer: TemplateRendererPort,
    secrets: _StaticSecrets,
    blob: _MemoryBlob,
) -> dict[str, Any]:
    uow_factory = _uow_factory_with_store(store)
    common = {
        "router": NotificationRouter(),
        "renderer": renderer,
        "notifier": notifier,
        "secrets": secrets,
        "blob": blob,
    }
    return {
        **common,
        "change": HandleChangeEventUseCase(uow_factory, **common),
        "error": HandleErrorEventUseCase(uow_factory, **common),
        "stale": HandleStaleEventUseCase(uow_factory, **common),
        "test_notify": SendTestNotificationUseCase(
            uow_factory,
            renderer=renderer,
            notifier=notifier,
            secrets=secrets,
        ),
    }


# ---------------------------------------------------------------------------
# PublishOutboxUseCase
# ---------------------------------------------------------------------------


async def test_given_unsent_outbox_rows_when_publish_then_marks_sent() -> None:
    store = reset_in_memory_store()
    uow = InMemoryUnitOfWork(store=store)
    now = uow.now()
    row_id = uow.new_id()
    await uow.outbox.add(
        id=row_id,
        aggregate_type="url",
        aggregate_id=uuid4(),
        event_type="UrlChangeDetected",
        event_id=uuid4(),
        payload={"url_id": str(uuid4()), "change_id": str(uuid4())},
        created_at=now,
    )
    await uow.commit()
    publisher = _CapturingPublisher()

    result = await _PublishOutbox(_uow_factory_with_store(store), publisher).execute({})

    assert result == {"published": 1, "failed": 0}
    assert publisher.published[0]["exchange"] == "events"
    assert publisher.published[0]["routing_key"] == "url.changed"
    fresh_uow = InMemoryUnitOfWork(store=store)
    unsent = await fresh_uow.outbox.list_unsent(limit=10)
    assert unsent == []


async def test_given_publish_failure_when_publish_then_increments_attempts() -> None:
    store = reset_in_memory_store()
    uow = InMemoryUnitOfWork(store=store)
    now = uow.now()
    await uow.outbox.add(
        id=uow.new_id(),
        aggregate_type="url",
        aggregate_id=uuid4(),
        event_type="UrlChangeDetected",
        event_id=uuid4(),
        payload={"url_id": str(uuid4())},
        created_at=now,
    )
    await uow.commit()
    publisher = _CapturingPublisher(fail_first=1)

    result = await _PublishOutbox(_uow_factory_with_store(store), publisher).execute({})

    assert result == {"published": 0, "failed": 1}
    fresh_uow = InMemoryUnitOfWork(store=store)
    unsent = await fresh_uow.outbox.list_unsent(limit=10)
    assert len(unsent) == 1
    assert unsent[0]["attempts"] == 1


async def test_given_config_aggregate_when_publish_then_uses_fanout_exchange() -> None:
    store = reset_in_memory_store()
    uow = InMemoryUnitOfWork(store=store)
    await uow.outbox.add(
        id=uow.new_id(),
        aggregate_type="config",
        aggregate_id=uuid4(),
        event_type="ConfigChanged",
        event_id=uuid4(),
        payload={"key": "LOG_LEVEL", "value": "INFO", "version": 1},
        created_at=uow.now(),
    )
    await uow.commit()
    publisher = _CapturingPublisher()

    await _PublishOutbox(_uow_factory_with_store(store), publisher).execute({})

    assert publisher.published[0]["exchange"] == "config"
    assert publisher.published[0]["routing_key"] == ""


# ---------------------------------------------------------------------------
# HandleChangeEventUseCase
# ---------------------------------------------------------------------------


async def test_given_change_event_with_global_binding_when_handle_then_delivers_once() -> None:
    store = reset_in_memory_store()
    notifier = _RecordingNotifier()
    blob = _MemoryBlob()
    secrets = _StaticSecrets()
    world = await _seed_world(store)
    components = _build_handler_components(
        store,
        notifier=notifier,
        renderer=_StaticRenderer(),
        secrets=secrets,
        blob=blob,
    )

    result = await components["change"].execute(_event_envelope(world))

    assert result.delivered == 1
    assert result.skipped == 0
    assert result.failed == 0
    assert notifier.sent[0]["channel_kind"] == "webhook"
    assert notifier.sent[0]["apprise_url"] == f"json://{world['channel'].id}/notify"
    assert notifier.sent[0]["template"] == "urlchangedetected.txt"


async def test_given_duplicate_event_when_handle_then_dedups() -> None:
    store = reset_in_memory_store()
    notifier = _RecordingNotifier()
    blob = _MemoryBlob()
    secrets = _StaticSecrets()
    world = await _seed_world(store)
    components = _build_handler_components(
        store,
        notifier=notifier,
        renderer=_StaticRenderer(),
        secrets=secrets,
        blob=blob,
    )
    envelope = _event_envelope(world)

    first = await components["change"].execute(envelope)
    second = await components["change"].execute(envelope)

    assert first.delivered == 1
    assert second.delivered == 0
    assert second.skipped == 1
    assert len(notifier.sent) == 1


async def test_given_on_change_disabled_when_handle_change_then_no_channels() -> None:
    store = reset_in_memory_store()
    notifier = _RecordingNotifier()
    blob = _MemoryBlob()
    secrets = _StaticSecrets()
    world = await _seed_world(store, on_change=False, on_error=True)
    components = _build_handler_components(
        store,
        notifier=notifier,
        renderer=_StaticRenderer(),
        secrets=secrets,
        blob=blob,
    )

    result = await components["change"].execute(_event_envelope(world))

    assert result.no_channels is True
    assert notifier.sent == []


async def test_given_error_event_when_handle_error_then_delivers() -> None:
    store = reset_in_memory_store()
    notifier = _RecordingNotifier()
    blob = _MemoryBlob()
    secrets = _StaticSecrets()
    world = await _seed_world(store, on_change=False, on_error=True)
    components = _build_handler_components(
        store,
        notifier=notifier,
        renderer=_StaticRenderer(),
        secrets=secrets,
        blob=blob,
    )
    envelope = _event_envelope(
        world,
        type="UrlCrawlFailed",
        error="timeout",
        consecutive_errors=2,
    )

    result = await components["error"].execute(envelope)

    assert result.delivered == 1
    assert notifier.sent[0]["template"] == "urlcrawlfailed.txt"


async def test_given_stale_event_when_handle_stale_then_delivers() -> None:
    store = reset_in_memory_store()
    notifier = _RecordingNotifier()
    blob = _MemoryBlob()
    secrets = _StaticSecrets()
    world = await _seed_world(
        store,
        on_change=False,
        on_error=False,
        on_no_change=True,
    )
    components = _build_handler_components(
        store,
        notifier=notifier,
        renderer=_StaticRenderer(),
        secrets=secrets,
        blob=blob,
    )
    envelope = _event_envelope(world, type="UrlBecameStale")

    result = await components["stale"].execute(envelope)

    assert result.delivered == 1
    assert notifier.sent[0]["template"] == "urlbecamestale.txt"


async def test_given_send_failure_when_handle_then_records_failed() -> None:
    store = reset_in_memory_store()
    blob = _MemoryBlob()
    secrets = _StaticSecrets()
    world = await _seed_world(store)
    notifier = _RecordingNotifier(fail_for={world["channel"].id})
    components = _build_handler_components(
        store,
        notifier=notifier,
        renderer=_StaticRenderer(),
        secrets=secrets,
        blob=blob,
    )

    result = await components["change"].execute(_event_envelope(world))

    assert result.delivered == 0
    assert result.failed == 1
    uow = InMemoryUnitOfWork(store=store)
    rows = [r for r in uow._store.notification_log if r["channel_id"] == world["channel"].id]
    assert rows[0]["status"] == "failed"
    assert rows[0]["error"] == "simulated failure"


async def test_given_unknown_event_type_when_handle_then_no_channels() -> None:
    store = reset_in_memory_store()
    notifier = _RecordingNotifier()
    blob = _MemoryBlob()
    secrets = _StaticSecrets()
    world = await _seed_world(store)
    components = _build_handler_components(
        store,
        notifier=notifier,
        renderer=_StaticRenderer(),
        secrets=secrets,
        blob=blob,
    )
    envelope = _event_envelope(world, type="NoSuchEvent")

    result = await components["change"].execute(envelope)

    assert result.no_channels is True
    assert notifier.sent == []


# ---------------------------------------------------------------------------
# SendTestNotificationUseCase
# ---------------------------------------------------------------------------


async def test_given_existing_channel_when_test_notify_then_sends_and_returns_success() -> None:
    store = reset_in_memory_store()
    notifier = _RecordingNotifier()
    blob = _MemoryBlob()
    secrets = _StaticSecrets()
    world = await _seed_world(store)
    components = _build_handler_components(
        store,
        notifier=notifier,
        renderer=_StaticRenderer(),
        secrets=secrets,
        blob=blob,
    )

    result = await components["test_notify"].execute(world["channel"].id)

    assert result.success is True
    assert result.error is None
    assert result.channel_id == world["channel"].id
    assert notifier.sent[0]["template"] == "change.txt"


async def test_given_missing_channel_when_test_notify_then_raises_not_found() -> None:
    store = reset_in_memory_store()
    notifier = _RecordingNotifier()
    blob = _MemoryBlob()
    secrets = _StaticSecrets()
    components = _build_handler_components(
        store,
        notifier=notifier,
        renderer=_StaticRenderer(),
        secrets=secrets,
        blob=blob,
    )

    with pytest.raises(NotFoundError):
        await components["test_notify"].execute(uuid4())


async def test_given_send_failure_when_test_notify_then_returns_failure() -> None:
    store = reset_in_memory_store()
    blob = _MemoryBlob()
    secrets = _StaticSecrets()
    world = await _seed_world(store)
    notifier = _RecordingNotifier(fail_for={world["channel"].id})
    components = _build_handler_components(
        store,
        notifier=notifier,
        renderer=_StaticRenderer(),
        secrets=secrets,
        blob=blob,
    )

    result = await components["test_notify"].execute(world["channel"].id)

    assert result.success is False
    assert result.error == "simulated failure"
