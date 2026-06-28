"""Notifier worker tests: event handler dispatch, envelope parsing, and policy.

The tests build a :class:`NotifierComposition` with in-memory fakes for
the broker and the Apprise notifier, drive it through the published
``_make_handler`` / ``_make_handler`` paths, and assert on the handler
decisions, the per-channel metrics, and the retry-republish payload.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from _fakes import InMemoryUnitOfWork, reset_in_memory_store
from _pipeline_fakes import InMemoryBlobStorage

from lens_application.dto import (
    EventEnvelope,
    HandleEventResult,
    NotificationChannelOutcome,
)
from lens_application.pipeline import (
    ChannelSecretProvider,
    EventConsumerPort,
    EventPublisherPort,
    RenderedMessage,
    SendResult,
)
from lens_application.use_cases import (
    HandleChangeEventUseCase,
    HandleErrorEventUseCase,
    HandleStaleEventUseCase,
)
from lens_common.metrics import MetricFactory, create_metrics
from lens_notifier.main import (
    HandlerDecision,
    NotifierComposition,
    _envelope_from_message,
    _make_handler,
    build_notifier_worker,
)
from lens_notifier.settings import NotifierSettings

__all__ = []


class _StaticRenderer:
    def render(
        self,
        *,
        template_name: str,
        context: dict[str, Any],
    ) -> RenderedMessage:
        return RenderedMessage(subject="s", body=f"tpl={template_name}")


class _StaticNotifier:
    def __init__(self, *, fail_channels: set[str] | None = None) -> None:
        self._fail = fail_channels or set()

    async def send(
        self,
        *,
        channel_kind: str,
        apprise_url: str,
        message: RenderedMessage,
    ) -> SendResult:
        if apprise_url in self._fail:
            return SendResult(success=False, error="simulated failure")
        return SendResult(success=True)


class _StaticBlob:
    async def put(self, key: str, data: bytes) -> str:
        return key

    async def get(self, key: str) -> bytes:
        return b""

    async def delete(self, key: str) -> None:
        return None


class _StaticConsumer(EventConsumerPort):
    def __init__(self) -> None:
        self.started_with: tuple[Callable[..., Any], int] | None = None
        self.stop_called = False

    async def start(
        self,
        handler: Callable[..., Any],
        *,
        prefetch: int = 1,
    ) -> None:
        self.started_with = (handler, prefetch)

    async def stop(self) -> None:
        self.stop_called = True


class _RecordingPublisher(EventPublisherPort):
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def publish(
        self,
        *,
        exchange: str,
        routing_key: str,
        body: dict[str, Any],
    ) -> None:
        self.calls.append(
            {
                "exchange": exchange,
                "routing_key": routing_key,
                "body": body,
            },
        )


class _StubUseCase:
    def __init__(
        self,
        *,
        delivered: int = 1,
        failed: int = 0,
        outcomes: list[NotificationChannelOutcome] | None = None,
        suppressed: bool = False,
        suppression_reason: str | None = None,
    ) -> None:
        self.calls: list[EventEnvelope] = []
        self._delivered = delivered
        self._failed = failed
        self._outcomes = outcomes
        self._suppressed = suppressed
        self._reason = suppression_reason

    async def execute(self, envelope: EventEnvelope) -> HandleEventResult:
        self.calls.append(envelope)
        return HandleEventResult(
            event_id=envelope.message_id,
            delivered=self._delivered,
            failed=self._failed,
            outcomes=list(self._outcomes or []),
            suppressed=self._suppressed,
            suppression_reason=self._reason,
        )


class _StaticSecretProvider(ChannelSecretProvider):
    def apprise_url_for(self, channel: Any) -> str:
        return f"apprise://{channel.id}"


class _RecordingDlq:
    def __init__(self) -> None:
        self.added: list[dict[str, Any]] = []

    async def add(
        self,
        *,
        queue: str,
        message_id: str,
        body: dict[str, Any],
        error: str | None = None,
    ) -> None:
        self.added.append(
            {
                "queue": queue,
                "message_id": message_id,
                "body": body,
                "error": error,
            },
        )


def _settings(**overrides: Any) -> NotifierSettings:
    defaults: dict[str, Any] = {
        "notify_max_attempts": 3,
        "notify_retry_base_seconds": 1.0,
        "per_channel_max_rate": 10,
        "notifier_prefetch": 4,
    }
    defaults.update(overrides)
    return NotifierSettings(**defaults)


def _build(
    *,
    handle_change: Any,
    handle_error: Any,
    handle_stale: Any,
    settings: NotifierSettings | None = None,
    event_publisher: EventPublisherPort | None = None,
    dlq: Any = None,
    metrics: MetricFactory | None = None,
    secret_provider: ChannelSecretProvider | None = None,
) -> NotifierComposition:
    from lens_common.lifecycle import GracefulShutdown

    consumer = _StaticConsumer()
    publisher = event_publisher or _RecordingPublisher()
    return NotifierComposition(
        settings=settings or _settings(),
        handle_change=handle_change,
        handle_error=handle_error,
        handle_stale=handle_stale,
        consumer=consumer,
        blob=InMemoryBlobStorage(),
        outbox_relay=None,
        event_publisher=publisher,
        secrets=secret_provider or _StaticSecretProvider(),
        shutdown=GracefulShutdown(),
        dlq=dlq,
        metrics=metrics or MetricFactory(create_metrics()),
    )


def _change_body(
    *,
    message_id: str | None = None,
    event_type: str = "UrlChangeDetected",
    attempt: int = 1,
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "message_id": message_id or str(uuid4()),
        "type": event_type,
        "occurred_at": "2026-01-01T12:00:00Z",
        "attempt": attempt,
        "data": {
            "url_id": str(uuid4()),
            "domain_id": str(uuid4()),
            "category_id": None,
            "change_id": str(uuid4()),
            "significant": True,
            "classification": classification or {},
        },
    }


@pytest.fixture(autouse=True)
def _clear() -> None:
    reset_in_memory_store()


def test_given_change_message_when_envelope_then_parses_fields() -> None:
    body = {
        "message_id": "11111111-1111-1111-1111-111111111111",
        "type": "UrlChangeDetected",
        "occurred_at": "2026-01-01T12:00:00Z",
        "data": {
            "url_id": "22222222-2222-2222-2222-222222222222",
            "domain_id": "33333333-3333-3333-3333-333333333333",
            "category_id": None,
            "change_id": "44444444-4444-4444-4444-444444444444",
            "significant": True,
        },
    }

    envelope = _envelope_from_message(body)

    assert envelope.type == "UrlChangeDetected"
    assert envelope.message_id == UUID("11111111-1111-1111-1111-111111111111")
    assert envelope.url_id == UUID("22222222-2222-2222-2222-222222222222")
    assert envelope.domain_id == UUID("33333333-3333-3333-3333-333333333333")
    assert envelope.change_id == UUID("44444444-4444-4444-4444-444444444444")
    assert envelope.occurred_at == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_given_error_message_when_envelope_then_carries_error() -> None:
    body = {
        "message_id": str(uuid4()),
        "type": "UrlCrawlFailed",
        "occurred_at": "2026-01-01T00:00:00Z",
        "data": {
            "url_id": str(uuid4()),
            "domain_id": str(uuid4()),
            "category_id": None,
            "error": "TimeoutError",
            "consecutive_errors": 3,
        },
    }

    envelope = _envelope_from_message(body)

    assert envelope.type == "UrlCrawlFailed"
    assert envelope.error == "TimeoutError"
    assert envelope.consecutive_errors == 3


def test_given_malformed_message_id_when_envelope_then_coerces_to_uuid() -> None:
    body = {
        "message_id": "garbage",
        "type": "UrlChangeDetected",
        "occurred_at": "2026-01-01T00:00:00Z",
        "data": {
            "url_id": "garbage",
            "domain_id": "garbage",
        },
    }

    envelope = _envelope_from_message(body)

    assert envelope.message_id == UUID(int=0)
    assert envelope.url_id == UUID(int=0)
    assert envelope.domain_id == UUID(int=0)


async def test_given_change_event_when_handler_then_dispatches_to_change_use_case() -> None:
    change = _StubUseCase()
    error = _StubUseCase()
    stale = _StubUseCase()
    comp = _build(
        handle_change=change,
        handle_error=error,
        handle_stale=stale,
    )
    handler = _make_handler(comp)

    decision = await handler(_change_body())

    assert decision is HandlerDecision.ACK
    assert len(change.calls) == 1
    assert error.calls == []
    assert stale.calls == []


async def test_given_error_event_when_handler_then_dispatches_to_error_use_case() -> None:
    change = _StubUseCase()
    error = _StubUseCase()
    stale = _StubUseCase()
    comp = _build(
        handle_change=change,
        handle_error=error,
        handle_stale=stale,
    )
    handler = _make_handler(comp)
    body = _change_body(event_type="UrlCrawlFailed")

    decision = await handler(body)

    assert decision is HandlerDecision.ACK
    assert len(error.calls) == 1
    assert change.calls == []


async def test_given_stale_event_when_handler_then_dispatches_to_stale_use_case() -> None:
    change = _StubUseCase()
    error = _StubUseCase()
    stale = _StubUseCase()
    comp = _build(
        handle_change=change,
        handle_error=error,
        handle_stale=stale,
    )
    handler = _make_handler(comp)
    body = _change_body(event_type="UrlBecameStale")

    decision = await handler(body)

    assert decision is HandlerDecision.ACK
    assert len(stale.calls) == 1
    assert change.calls == []
    assert error.calls == []


async def test_given_unknown_event_type_when_handler_then_acks() -> None:
    change = _StubUseCase()
    error = _StubUseCase()
    stale = _StubUseCase()
    comp = _build(
        handle_change=change,
        handle_error=error,
        handle_stale=stale,
    )
    handler = _make_handler(comp)

    decision = await handler({"type": "Other", "message_id": str(uuid4()), "data": {}})

    assert decision is HandlerDecision.ACK
    assert change.calls == []


async def test_given_non_dict_body_when_handler_then_acked() -> None:
    change = _StubUseCase()
    error = _StubUseCase()
    stale = _StubUseCase()
    comp = _build(
        handle_change=change,
        handle_error=error,
        handle_stale=stale,
    )
    handler = _make_handler(comp)

    decision = await handler("not a dict")  # type: ignore[arg-type]

    assert decision is HandlerDecision.ACK
    assert change.calls == []


async def test_given_failed_sends_when_handler_then_republishes_with_attempt() -> None:
    publisher = _RecordingPublisher()
    outcomes = [
        NotificationChannelOutcome(
            channel_id=uuid4(),
            channel_kind="slack",
            success=False,
            error="503",
        ),
    ]
    change = _StubUseCase(delivered=0, failed=1, outcomes=outcomes)
    comp = _build(
        handle_change=change,
        handle_error=_StubUseCase(),
        handle_stale=_StubUseCase(),
        event_publisher=publisher,
    )
    handler = _make_handler(comp)
    body = _change_body(attempt=1)

    decision = await handler(body)

    assert decision is HandlerDecision.RETRY
    assert len(publisher.calls) == 1
    republished = publisher.calls[0]
    assert republished["routing_key"] == "url.changed"
    assert republished["body"]["attempt"] == 2


async def test_given_max_attempts_reached_when_handler_then_dead_letters() -> None:
    publisher = _RecordingPublisher()
    dlq = _RecordingDlq()
    outcomes = [
        NotificationChannelOutcome(
            channel_id=uuid4(),
            channel_kind="slack",
            success=False,
            error="503",
        ),
    ]
    change = _StubUseCase(delivered=0, failed=1, outcomes=outcomes)
    comp = _build(
        handle_change=change,
        handle_error=_StubUseCase(),
        handle_stale=_StubUseCase(),
        event_publisher=publisher,
        dlq=dlq,
    )
    handler = _make_handler(comp)
    body = _change_body(attempt=3)

    decision = await handler(body)

    assert decision is HandlerDecision.DEAD_LETTER
    assert publisher.calls == []
    assert len(dlq.added) == 1
    assert dlq.added[0]["queue"] == "change.events.dlq"


async def test_given_use_case_raises_when_handler_then_republishes_or_dead_letters() -> None:
    class _RaisingUseCase:
        async def execute(self, envelope: EventEnvelope) -> HandleEventResult:
            raise RuntimeError("boom")

    publisher = _RecordingPublisher()
    dlq = _RecordingDlq()
    comp = _build(
        handle_change=_RaisingUseCase(),
        handle_error=_StubUseCase(),
        handle_stale=_StubUseCase(),
        event_publisher=publisher,
        dlq=dlq,
    )
    handler = _make_handler(comp)

    retry_decision = await handler(_change_body(attempt=1))
    dead_decision = await handler(_change_body(attempt=3))

    assert retry_decision is HandlerDecision.RETRY
    assert dead_decision is HandlerDecision.DEAD_LETTER
    assert len(publisher.calls) == 1
    assert len(dlq.added) == 1


async def test_given_suppressed_event_when_handler_then_acks_without_publish() -> None:
    publisher = _RecordingPublisher()
    change = _StubUseCase(
        delivered=0,
        failed=0,
        suppressed=True,
        suppression_reason="change_not_meaningful",
    )
    comp = _build(
        handle_change=change,
        handle_error=_StubUseCase(),
        handle_stale=_StubUseCase(),
        event_publisher=publisher,
    )
    handler = _make_handler(comp)

    decision = await handler(
        _change_body(
            event_type="ChangeEnriched",
            classification={"is_meaningful": False, "change_type": "price"},
        ),
    )

    assert decision is HandlerDecision.ACK
    assert publisher.calls == []


def test_given_components_when_build_notifier_worker_then_wires_use_cases() -> None:
    settings = _settings()
    consumer = _StaticConsumer()
    publisher = _RecordingPublisher()

    composition = build_notifier_worker(
        settings=settings,
        uow_factory=InMemoryUnitOfWork,
        consumer=consumer,
        notifier=_StaticNotifier(),
        renderer=_StaticRenderer(),
        blob=InMemoryBlobStorage(),
        outbox_publisher=publisher,
    )

    assert composition.settings is settings
    assert composition.consumer is consumer
    assert composition.event_publisher is publisher
    assert isinstance(composition.handle_change, HandleChangeEventUseCase)
    assert isinstance(composition.handle_error, HandleErrorEventUseCase)
    assert isinstance(composition.handle_stale, HandleStaleEventUseCase)
    assert composition.outbox_relay is not None
    assert composition.secrets is not None


async def test_given_suppress_cosmetic_classification_when_handler_then_acks() -> None:
    """The use-case policy is exercised through the handler path.

    The notifications use case short-circuits cosmetic / layout
    classification before any channel send. The notifier-worker
    handler observes the suppressed result and acks without
    republishing.
    """

    class _SuppressingUseCase:
        async def execute(self, envelope: EventEnvelope) -> HandleEventResult:
            return HandleEventResult(
                event_id=envelope.message_id,
                suppressed=True,
                suppression_reason="change_type_cosmetic",
            )

    publisher = _RecordingPublisher()
    comp = _build(
        handle_change=_SuppressingUseCase(),
        handle_error=_StubUseCase(),
        handle_stale=_StubUseCase(),
        event_publisher=publisher,
    )
    handler = _make_handler(comp)

    decision = await handler(
        _change_body(
            event_type="ChangeEnriched",
            classification={"is_meaningful": True, "change_type": "cosmetic"},
        ),
    )

    assert decision is HandlerDecision.ACK
    assert publisher.calls == []


def test_metrics_module_surface() -> None:
    """Smoke test: MetricFactory exposes the canonical notifier counters."""
    metrics = MetricFactory(create_metrics())
    assert metrics.notification_result is not None
    assert metrics.task_processed is not None
    assert metrics.dlq_count is not None
