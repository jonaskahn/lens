"""Notification use cases.

These use cases cover the full notification delivery path:

* :class:`PublishOutboxUseCase` - drains the outbox to the broker.
* :class:`HandleChangeEventUseCase` - routes + renders + sends a
  ``UrlChangeDetected`` event (or error/stale variants).
* :class:`HandleErrorEventUseCase` - handles ``UrlCrawlFailed``.
* :class:`HandleStaleEventUseCase` - handles ``UrlBecameStale``.
* :class:`SendTestNotificationUseCase` - sends a sample message to a single
  channel without a real event.

All notification use cases are pure application logic: they orchestrate
the domain ``NotificationRouter``, the :class:`TemplateRendererPort`, the
:class:`NotifierPort`, and the :class:`NotificationLogRepository` dedup
table. No broker / Apprise code is imported here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from lens_application.dto import (
    EventEnvelope,
    HandleEventResult,
    NotificationChannelOutcome,
    SendTestNotificationResult,
)
from lens_application.pipeline import (
    BlobStoragePort,
    NotifierPort,
    RenderedMessage,
    TemplateRendererPort,
)
from lens_application.pipeline import (
    ChannelSecretProvider as _ChannelSecretProvider,
)
from lens_application.ports import (
    IdempotencyPort,
    ThrottlePort,
    UnitOfWork,
)
from lens_application.use_cases._base import UseCase
from lens_domain.entities import Channel, ChannelBinding
from lens_domain.enums import TriggerType
from lens_domain.services import NotificationRouter, RouterRequest

__all__ = [
    "HandleChangeEventUseCase",
    "HandleErrorEventUseCase",
    "HandleStaleEventUseCase",
    "PublishOutboxUseCase",
    "SendTestNotificationUseCase",
]


_TRIGGER_FOR_EVENT: dict[str, TriggerType] = {
    "UrlChangeDetected": TriggerType.ON_CHANGE,
    "UrlCrawlFailed": TriggerType.ON_ERROR,
    "UrlBecameStale": TriggerType.ON_NO_CHANGE,
    "SiteTemplateDriftDetected": TriggerType.ON_CHANGE,
    "ChangeEnriched": TriggerType.ON_CHANGE,
}


@dataclass(frozen=True, slots=True)
class _DeliveryContext:
    """The collaborators an event handler needs to deliver a message."""

    event_id: UUID
    trigger: TriggerType
    template: str
    template_context: dict[str, Any]
    url_id: UUID
    domain_id: UUID
    category_id: UUID | None


@dataclass(frozen=True, slots=True)
class _NotifyPolicyDecision:
    """The outcome of the per-event delivery policy check.

    ``suppress=True`` means the event should be dropped without sending
    to any channel; ``reason`` is a short, machine-readable tag carried
    through to the worker for logging and metrics.
    """

    suppress: bool
    reason: str | None


class _HandleEventBase(UseCase[EventEnvelope, HandleEventResult]):
    """Shared orchestration for change / error / stale event variants."""

    def __init__(
        self,
        uow_factory: Any,
        *,
        router: NotificationRouter,
        renderer: TemplateRendererPort,
        notifier: NotifierPort,
        secrets: _ChannelSecretProvider,
        blob: BlobStoragePort,
        diff_snippet_lines: int = 50,
        throttle: ThrottlePort | None = None,
        idempotency: IdempotencyPort | None = None,
    ) -> None:
        super().__init__(uow_factory)
        self._router = router
        self._renderer = renderer
        self._notifier = notifier
        self._secrets = secrets
        self._blob = blob
        self._diff_lines = diff_snippet_lines
        self._throttle = throttle
        self._idempotency = idempotency

    async def run(self, event: EventEnvelope, uow: UnitOfWork) -> HandleEventResult:
        trigger = _TRIGGER_FOR_EVENT.get(event.type)
        if trigger is None:
            return HandleEventResult(
                event_id=event.message_id,
                no_channels=True,
            )
        decision = self._classify(event)
        if decision.suppress:
            return HandleEventResult(
                event_id=event.message_id,
                no_channels=True,
                suppressed=True,
                suppression_reason=decision.reason,
            )
        ctx = _DeliveryContext(
            event_id=event.message_id,
            trigger=trigger,
            template=f"{event.type.lower()}.txt",
            template_context=await self._build_context(uow, event),
            url_id=event.url_id,
            domain_id=event.domain_id,
            category_id=event.category_id,
        )
        return await self._deliver(ctx, uow)

    @staticmethod
    def _classify(event: EventEnvelope) -> _NotifyPolicyDecision:
        """Apply the notifier's delivery policy to a single event.

        Phase-5 notify mode (``ai_enrich_hold_seconds``) plus the cosmetic
        suppression rule: ``is_meaningful=False`` or
        ``change_type in {"cosmetic", "layout"}`` is dropped at the worker
        layer (the use case is invoked from the in-process consumer, so
        the policy lives here for re-use in tests and any other entry
        point such as the test-notify CLI).
        """
        classification = event.classification or {}
        change_type = classification.get("change_type")
        is_meaningful = classification.get("is_meaningful")
        if event.type == "ChangeEnriched" and is_meaningful is False:
            return _NotifyPolicyDecision(
                suppress=True,
                reason="change_not_meaningful",
            )
        if change_type in {"cosmetic", "layout"}:
            return _NotifyPolicyDecision(
                suppress=True,
                reason=f"change_type_{change_type}",
            )
        return _NotifyPolicyDecision(suppress=False, reason=None)

    async def _build_context(self, uow: UnitOfWork, event: EventEnvelope) -> dict[str, Any]:
        url = await uow.urls.get(event.url_id)
        domain = await uow.domains.get(event.domain_id)
        category = None
        if event.category_id is not None:
            category = await uow.categories.get(event.category_id)
        change_payload: dict[str, Any] = {}
        diff_snippet = ""
        if event.change_id is not None:
            change = await uow.changes.get(event.change_id)
            if change is not None:
                change_payload = {
                    "added_count": change.diff_summary.added_count,
                    "removed_count": change.diff_summary.removed_count,
                    "semantic_score": change.semantic_score,
                    "significant": change.significant,
                    "created_at": change.created_at.isoformat(),
                }
                if change.diff_ref is not None:
                    try:
                        diff_bytes = await self._blob.get(change.diff_ref)
                        diff_snippet = self._snippet(diff_bytes.decode("utf-8"))
                    except Exception:
                        diff_snippet = ""
        return {
            "url": url.address.value if url is not None else "",
            "domain": domain.host.value if domain is not None else "",
            "category": category.name if category is not None else None,
            "change": change_payload,
            "diff_snippet": diff_snippet,
            "error": event.error or "",
            "checked_at": event.occurred_at.isoformat(),
            "app_name": "lens",
            "classification": event.classification or {},
        }

    def _snippet(self, diff_text: str) -> str:
        lines = diff_text.splitlines()
        return "\n".join(lines[: self._diff_lines])

    async def _deliver(self, ctx: _DeliveryContext, uow: UnitOfWork) -> HandleEventResult:
        bindings, channels = await self._load_targets(uow, ctx)
        request = RouterRequest(
            url_id=ctx.url_id,
            domain_id=ctx.domain_id,
            category_id=ctx.category_id,
            trigger=ctx.trigger,
            bindings=tuple(bindings),
            channels=channels,
        )
        targets = self._router.route(request)
        if not targets:
            return HandleEventResult(event_id=ctx.event_id, no_channels=True)
        delivered = 0
        skipped = 0
        failed = 0
        outcomes: list[NotificationChannelOutcome] = []
        for channel in targets:
            channel_key = f"channel:{channel.kind.value}:{channel.id}"
            if self._idempotency is not None:
                dedup_key = f"notification:{ctx.event_id}:{channel.id}"
                if await self._idempotency.is_seen(dedup_key):
                    skipped += 1
                    continue
            if self._throttle is not None:
                await self._throttle.acquire(channel_key)
            seen = await uow.notification_log.seen(
                event_id=ctx.event_id,
                channel_id=channel.id,
            )
            if seen:
                skipped += 1
                continue
            message: RenderedMessage = self._renderer.render(
                template_name=ctx.template,
                context=ctx.template_context,
            )
            result = await self._notifier.send(
                channel_kind=channel.kind.value,
                apprise_url=self._secrets.apprise_url_for(channel),
                message=message,
            )
            await uow.notification_log.record(
                event_id=ctx.event_id,
                channel_id=channel.id,
                status="sent" if result.success else "failed",
                error=result.error,
                sent_at=uow.now(),
            )
            if self._idempotency is not None:
                await self._idempotency.mark_seen(f"notification:{ctx.event_id}:{channel.id}")
            outcomes.append(
                NotificationChannelOutcome(
                    channel_id=channel.id,
                    channel_kind=channel.kind.value,
                    success=result.success,
                    error=result.error,
                ),
            )
            if result.success:
                delivered += 1
            else:
                failed += 1
        return HandleEventResult(
            event_id=ctx.event_id,
            delivered=delivered,
            skipped=skipped,
            failed=failed,
            outcomes=outcomes,
        )

    async def _load_targets(
        self, uow: UnitOfWork, ctx: _DeliveryContext
    ) -> tuple[list[ChannelBinding], dict[UUID, Channel]]:
        url = await uow.urls.get(ctx.url_id)
        if url is None:
            return [], {}
        bindings: list[ChannelBinding] = []
        global_bindings, _ = await uow.channel_bindings.list(scope="global")
        bindings.extend(global_bindings)
        domain_bindings, _ = await uow.channel_bindings.list(
            scope="domain",
            scope_id=ctx.domain_id,
        )
        bindings.extend(domain_bindings)
        if ctx.category_id is not None:
            cat_bindings, _ = await uow.channel_bindings.list(
                scope="category",
                scope_id=ctx.category_id,
            )
            bindings.extend(cat_bindings)
        url_bindings, _ = await uow.channel_bindings.list(
            scope="url",
            scope_id=ctx.url_id,
        )
        bindings.extend(url_bindings)
        channel_ids = {b.channel_id for b in bindings}
        channels: dict[UUID, Channel] = {}
        for channel_id in channel_ids:
            channel = await uow.channels.get(channel_id)
            if channel is None:
                continue
            channels[channel.id] = channel
        return bindings, channels


class HandleChangeEventUseCase(_HandleEventBase):
    """Handle a ``UrlChangeDetected`` (or drift / enriched) event."""


class HandleErrorEventUseCase(_HandleEventBase):
    """Handle a ``UrlCrawlFailed`` event."""


class HandleStaleEventUseCase(_HandleEventBase):
    """Handle a ``UrlBecameStale`` event."""


class PublishOutboxUseCase(UseCase[dict[str, Any], dict[str, int]]):
    """Drain unsent outbox rows to the broker.

    The relay loops: claim a batch of unsent rows (one ``id`` each),
    publish each to ``publish_to_exchange`` / ``routing_key`` (taken from
    the payload's ``event_type``), and mark the row sent on success.
    Failed publishes increment ``attempts`` so the next tick retries.
    """

    def __init__(
        self,
        uow_factory: Any,
        publisher: Any,
        *,
        batch_size: int = 100,
    ) -> None:
        super().__init__(uow_factory)
        self._publisher = publisher
        self._batch_size = batch_size

    async def run(self, params: dict[str, Any], uow: UnitOfWork) -> dict[str, int]:
        rows = await uow.outbox.list_unsent(limit=self._batch_size)
        published_ids: list[UUID] = []
        failed_ids: list[UUID] = []
        for row in rows:
            event_type = row["event_type"]
            aggregate_type = row["aggregate_type"]
            routing_key = self._routing_key_for(aggregate_type, event_type)
            exchange = self._exchange_for(aggregate_type)
            attempts = int(row.get("attempts", 0))
            body = {
                "message_id": str(row["event_id"]),
                "type": event_type,
                "occurred_at": row["created_at"].isoformat(),
                "attempt": attempts + 1,
                "data": row["payload"],
            }
            try:
                await self._publisher.publish(
                    exchange=exchange,
                    routing_key=routing_key,
                    body=body,
                )
            except Exception:
                failed_ids.append(row["id"])
                continue
            published_ids.append(row["id"])
        if published_ids:
            await uow.outbox.mark_sent(published_ids, sent_at=uow.now())
        if failed_ids:
            await uow.outbox.increment_attempts(failed_ids)
        return {
            "published": len(published_ids),
            "failed": len(failed_ids),
        }

    @staticmethod
    def _exchange_for(aggregate_type: str) -> str:
        if aggregate_type == "config":
            return "config"
        if aggregate_type == "change":
            return "enrich"
        return "events"

    @staticmethod
    def _routing_key_for(aggregate_type: str, event_type: str) -> str:
        if aggregate_type == "config":
            return ""
        if aggregate_type == "change":
            return "change.enrich"
        mapping: dict[str, str] = {
            "UrlChangeDetected": "url.changed",
            "UrlCrawlFailed": "url.failed",
            "UrlBecameStale": "url.stale",
            "SiteTemplateDriftDetected": "site.drift",
            "ChangeEnriched": "change.enriched",
        }
        return mapping.get(event_type, "url.event")


class SendTestNotificationUseCase(UseCase[UUID, SendTestNotificationResult]):
    """Render and send a sample notification to one channel.

    Used by the CLI's ``test-notify`` command to verify a channel's
    configuration. Does not require a real domain event; a synthetic
    context is built from the channel's most recent URL (if any) or from
    fixed placeholders.
    """

    def __init__(
        self,
        uow_factory: Any,
        *,
        renderer: TemplateRendererPort,
        notifier: NotifierPort,
        secrets: _ChannelSecretProvider,
    ) -> None:
        super().__init__(uow_factory)
        self._renderer = renderer
        self._notifier = notifier
        self._secrets = secrets

    async def run(self, channel_id: UUID, uow: UnitOfWork) -> SendTestNotificationResult:
        channel = await uow.channels.get(channel_id)
        if channel is None:
            from lens_application.errors import NotFoundError

            raise NotFoundError(f"channel not found: {channel_id!s}")
        context = {
            "url": "https://example.test/sample",
            "domain": "example.test",
            "category": "sample",
            "change": {
                "added_count": 1,
                "removed_count": 0,
                "semantic_score": 0.0,
                "significant": True,
                "created_at": uow.now().isoformat(),
            },
            "diff_snippet": "+ this is a sample diff line for test-notify\n",
            "error": "",
            "checked_at": uow.now().isoformat(),
            "app_name": "lens",
            "classification": {},
        }
        message = self._renderer.render(template_name="change.txt", context=context)
        result = await self._notifier.send(
            channel_kind=channel.kind.value,
            apprise_url=self._secrets.apprise_url_for(channel),
            message=message,
        )
        return SendTestNotificationResult(
            channel_id=channel.id,
            channel_kind=channel.kind.value,
            success=result.success,
            error=result.error,
        )
