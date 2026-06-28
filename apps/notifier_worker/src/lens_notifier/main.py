"""Composition root for the notifier worker role.

Wires throttle, idempotency, retry / DLQ routing, graceful shutdown,
bounded metrics, and a per-event notify-mode policy into the
notification delivery path. The worker is a thin runtime over
:class:`HandleChangeEventUseCase` /
:class:`HandleErrorEventUseCase` /
:class:`HandleStaleEventUseCase`: it deserializes an event envelope,
invokes the matching use case, and translates the returned status into
a broker action (ack, requeue with capped exponential backoff and
``attempt + 1``, or dead-letter).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from lens_application.dto import (
    EventEnvelope,
    HandleEventResult,
    NotificationChannelOutcome,
)
from lens_application.pipeline import (
    BlobStoragePort,
    ChannelSecretProvider,
    EventConsumerPort,
    EventPublisherPort,
    NotifierPort,
    TemplateRendererPort,
)
from lens_application.ports import (
    DeadLetterRepositoryPort,
    IdempotencyPort,
    ThrottlePort,
    UnitOfWork,
)
from lens_application.use_cases import (
    HandleChangeEventUseCase,
    HandleErrorEventUseCase,
    HandleStaleEventUseCase,
)
from lens_common.config import load_settings
from lens_common.lifecycle import GracefulShutdown
from lens_common.logging import configure_logging, get_logger
from lens_common.metrics import MetricFactory, create_metrics
from lens_common.retry import backoff_sleep_seconds
from lens_domain.services import NotificationRouter
from lens_infrastructure.outbox_relay import OutboxRelay, OutboxRelaySettings
from lens_infrastructure.secret_provider import ChannelSecretProvider as _DefaultChannelSecretProvider
from lens_notifier.settings import NotifierSettings

__all__ = [
    "HandlerDecision",
    "NotifierComposition",
    "build_notifier_worker",
    "run",
]

_logger = get_logger("lens_notifier")

_CHANGE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "UrlChangeDetected",
        "ChangeEnriched",
        "SiteTemplateDriftDetected",
    },
)

_NIL_UUID: UUID = UUID(int=0)


class HandlerDecision(StrEnum):
    """Action a worker handler returns after processing one event."""

    ACK = "ack"
    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True, slots=True)
class NotifierComposition:
    """Wiring container for the notifier worker role.

    Holds the settings, the three event use cases, the broker consumer,
    the outbox publisher used both by the relay and the
    retry-republish path, the optional Redis-backed collaborators, and
    the lifecycle coordinator. Frozen so callers cannot mutate the
    wiring after construction.
    """

    settings: NotifierSettings
    handle_change: HandleChangeEventUseCase
    handle_error: HandleErrorEventUseCase
    handle_stale: HandleStaleEventUseCase
    consumer: EventConsumerPort
    blob: BlobStoragePort
    outbox_relay: OutboxRelay | None
    event_publisher: EventPublisherPort | None
    secrets: ChannelSecretProvider
    shutdown: GracefulShutdown
    throttle: ThrottlePort | None = None
    idempotency: IdempotencyPort | None = None
    dlq: DeadLetterRepositoryPort | None = None
    metrics: MetricFactory | None = None


def build_notifier_worker(
    *,
    settings: NotifierSettings,
    uow_factory: Callable[[], UnitOfWork],
    consumer: EventConsumerPort,
    notifier: NotifierPort,
    renderer: TemplateRendererPort,
    blob: BlobStoragePort,
    outbox_publisher: EventPublisherPort,
    event_publisher: EventPublisherPort | None = None,
    secret_provider: ChannelSecretProvider | None = None,
    outbox_relay: OutboxRelay | None = None,
    throttle: ThrottlePort | None = None,
    idempotency: IdempotencyPort | None = None,
    dlq: DeadLetterRepositoryPort | None = None,
    metrics: MetricFactory | None = None,
) -> NotifierComposition:
    """Build a :class:`NotifierComposition` with the canonical wiring.

    Args:
        settings: Notifier configuration (prefetch, batch sizes, retry
            base, max attempts, per-channel rate).
        uow_factory: Factory that produces a fresh :class:`UnitOfWork`.
        consumer: Broker consumer for ``change.events``.
        notifier: Apprise-backed notification transport.
        renderer: Jinja-backed :class:`TemplateRendererPort`.
        blob: Blob storage adapter (used for diff snippets).
        outbox_publisher: Publisher used by the outbox relay; also
            serves as the default retry-republish publisher when
            ``event_publisher`` is not supplied.
        event_publisher: Optional dedicated publisher used to re-publish
            events for retry / rate-limit delays. Falls back to
            ``outbox_publisher`` when not supplied.
        secret_provider: Optional :class:`ChannelSecretProvider`; the
            default :class:`ChannelSecretProvider` reads the decrypted
            URL from the :class:`Channel` entity.
        outbox_relay: Optional pre-built :class:`OutboxRelay`. When
            omitted, one is constructed from ``uow_factory`` and
            ``outbox_publisher``. Tests that do not need the relay can
            pass ``None`` and skip outbox-related behaviour.
        throttle: Optional per-channel throttle. When omitted, sends
            proceed without a token-bucket gate.
        idempotency: Optional Redis-backed dedup store.
        dlq: Optional dead-letter repository for the ``change.events``
            side.
        metrics: Optional pre-built :class:`MetricFactory`; one is
            constructed with a private registry when not supplied so
            multiple compositions in one process do not collide on the
            global Prometheus registry.

    Returns:
        A frozen :class:`NotifierComposition` ready for the run loop.
    """
    secrets = secret_provider or _DefaultChannelSecretProvider()
    router = NotificationRouter()
    relay = outbox_relay
    if relay is None and outbox_publisher is not None:
        relay = OutboxRelay(
            uow_factory,
            outbox_publisher,
            OutboxRelaySettings(
                tick_seconds=settings.notifier_poll_seconds,
                batch_size=settings.notifier_outbox_batch_size,
            ),
        )
    return NotifierComposition(
        settings=settings,
        handle_change=HandleChangeEventUseCase(
            uow_factory,
            router=router,
            renderer=renderer,
            notifier=notifier,
            secrets=secrets,
            blob=blob,
            throttle=throttle,
            idempotency=idempotency,
        ),
        handle_error=HandleErrorEventUseCase(
            uow_factory,
            router=router,
            renderer=renderer,
            notifier=notifier,
            secrets=secrets,
            blob=blob,
            throttle=throttle,
            idempotency=idempotency,
        ),
        handle_stale=HandleStaleEventUseCase(
            uow_factory,
            router=router,
            renderer=renderer,
            notifier=notifier,
            secrets=secrets,
            blob=blob,
            throttle=throttle,
            idempotency=idempotency,
        ),
        consumer=consumer,
        blob=blob,
        outbox_relay=relay,
        event_publisher=event_publisher or outbox_publisher,
        secrets=secrets,
        shutdown=GracefulShutdown(),
        throttle=throttle,
        idempotency=idempotency,
        dlq=dlq,
        metrics=metrics or MetricFactory(create_metrics()),
    )


def _coerce_uuid(value: Any, *, field: str) -> UUID:
    """Best-effort coercion of an on-the-wire value to :class:`UUID`.

    Accepts the wire-format string (with or without dashes) and falls
    back to the nil UUID for missing / unparseable values so the
    downstream repositories do not raise on a malformed body.
    """
    if isinstance(value, UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return UUID(value)
        except ValueError:
            return _NIL_UUID
    return _NIL_UUID


def _coerce_optional_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _envelope_from_message(body: dict[str, Any]) -> EventEnvelope:
    """Translate a broker body into a typed :class:`EventEnvelope`."""
    data = body.get("data", {})
    occurred_at = body.get("occurred_at")
    if not isinstance(occurred_at, str):
        occurred_at = datetime.now(UTC).isoformat()
    message_id = body.get("message_id")
    if not isinstance(message_id, str) or not message_id:
        message_id = str(uuid4())
    return EventEnvelope(
        message_id=_coerce_uuid(message_id, field="message_id"),
        type=body.get("type", ""),
        occurred_at=datetime.fromisoformat(occurred_at.replace("Z", "+00:00")),
        url_id=_coerce_uuid(data.get("url_id", _NIL_UUID), field="url_id"),
        domain_id=_coerce_uuid(data.get("domain_id", _NIL_UUID), field="domain_id"),
        category_id=_coerce_optional_uuid(data.get("category_id")),
        change_id=_coerce_optional_uuid(data.get("change_id")),
        significant=bool(data.get("significant", True)),
        error=data.get("error"),
        consecutive_errors=data.get("consecutive_errors"),
        classification=data.get("classification"),
    )


def _use_case_for(comp: NotifierComposition, event_type: str) -> Callable[..., Any] | None:
    """Return the matching handle use case for ``event_type``."""
    if event_type in _CHANGE_EVENT_TYPES:
        return comp.handle_change.execute
    if event_type == "UrlCrawlFailed":
        return comp.handle_error.execute
    if event_type == "UrlBecameStale":
        return comp.handle_stale.execute
    return None


def _retry_delay_seconds(settings: NotifierSettings, attempt: int) -> float:
    """Compute the capped exponential back-off for a retry attempt.

    Uses :func:`lens_common.retry.backoff_sleep_seconds` with
    ``notify_retry_base_seconds`` as the base, matching the spec for
    phase-4 task 1.
    """
    return backoff_sleep_seconds(
        attempt,
        base=settings.notify_retry_base_seconds,
    )


def _make_handler(
    comp: NotifierComposition,
) -> Callable[[dict[str, Any]], Awaitable[HandlerDecision]]:
    """Build the per-message handler that the broker consumer dispatches."""

    async def _handle(body: dict[str, Any]) -> HandlerDecision:
        if not isinstance(body, dict):
            return HandlerDecision.ACK
        event_type = body.get("type", "")
        attempt = max(int(body.get("attempt", 1)), 1)
        envelope = _envelope_from_message(body)
        executor = _use_case_for(comp, event_type)
        if executor is None:
            return HandlerDecision.ACK

        start = time.monotonic()
        metrics = comp.metrics
        if metrics is not None:
            metrics.in_flight.labels(app="notifier").inc()
        try:
            result = await executor(envelope)
            elapsed = time.monotonic() - start
            _emit_metrics(comp, event_type, result, elapsed)
            _log_dispatch(envelope, result)
            decision = await _resolve_decision(comp, body, envelope, result, attempt)
            if decision is HandlerDecision.RETRY:
                await _republish_for_retry(comp, body, attempt)
            return decision
        except Exception as exc:
            _logger.exception(
                "notifier_unhandled_error",
                event_id=str(envelope.message_id),
                event_type=event_type,
            )
            return await _handle_unhandled(comp, body, envelope, attempt, str(exc))
        finally:
            if metrics is not None:
                metrics.in_flight.labels(app="notifier").dec()

    return _handle


async def _resolve_decision(
    comp: NotifierComposition,
    body: dict[str, Any],
    envelope: EventEnvelope,
    result: HandleEventResult,
    attempt: int,
) -> HandlerDecision:
    """Translate a use-case result into a :class:`HandlerDecision`."""
    if result.suppressed:
        if comp.metrics is not None:
            comp.metrics.task_processed.labels(
                app="notifier",
                outcome="suppressed",
            ).inc()
        _logger.info(
            "notifier_suppressed",
            event_id=str(envelope.message_id),
            event_type=envelope.type,
            reason=result.suppression_reason or "policy",
        )
        return HandlerDecision.ACK
    if getattr(result, "failed", 0) <= 0:
        return HandlerDecision.ACK
    if attempt >= comp.settings.notify_max_attempts:
        if comp.dlq is not None:
            await comp.dlq.add(
                queue="change.events.dlq",
                message_id=str(envelope.message_id),
                body=body,
                error="max retries exceeded",
            )
        if comp.metrics is not None:
            comp.metrics.dlq_count.labels(queue="change.events.dlq").inc()
        return HandlerDecision.DEAD_LETTER
    return HandlerDecision.RETRY


async def _handle_unhandled(
    comp: NotifierComposition,
    body: dict[str, Any],
    envelope: EventEnvelope,
    attempt: int,
    error: str,
) -> HandlerDecision:
    """Pick a decision when the use case itself raised."""
    if attempt >= comp.settings.notify_max_attempts:
        if comp.dlq is not None:
            await comp.dlq.add(
                queue="change.events.dlq",
                message_id=str(envelope.message_id),
                body=body,
                error=error,
            )
        if comp.metrics is not None:
            comp.metrics.dlq_count.labels(queue="change.events.dlq").inc()
        return HandlerDecision.DEAD_LETTER
    await _republish_for_retry(comp, body, attempt)
    return HandlerDecision.RETRY


async def _republish_for_retry(
    comp: NotifierComposition,
    body: dict[str, Any],
    attempt: int,
) -> None:
    """Re-publish a failed event with ``attempt + 1`` for the next worker hop.

    Falls back to a ``change.events`` topic routing key (derived from
    the original event type) when the body does not already carry an
    ``exchange`` / ``routing_key`` pair. A best-effort ``asyncio.sleep``
    applies the exponential back-off so the broker can spread the load.
    """
    publisher = comp.event_publisher
    if publisher is None:
        return
    delay = _retry_delay_seconds(comp.settings, attempt)
    if delay > 0:
        await asyncio.sleep(delay)
    next_attempt = attempt + 1
    new_body = dict(body)
    new_body["attempt"] = next_attempt
    exchange = body.get("exchange", "events")
    routing_key = body.get("routing_key") or _routing_key_for(body.get("type", ""))
    try:
        await publisher.publish(
            exchange=exchange,
            routing_key=routing_key,
            body=new_body,
        )
    except Exception:
        _logger.exception(
            "notifier_republish_failed",
            event_id=str(body.get("message_id", _NIL_UUID)),
            attempt=next_attempt,
        )
        return
    if comp.metrics is not None:
        comp.metrics.task_processed.labels(
            app="notifier",
            outcome="retry",
        ).inc()
    _logger.info(
        "notifier_republished",
        event_id=str(body.get("message_id", _NIL_UUID)),
        attempt=next_attempt,
        delay_seconds=delay,
    )


def _routing_key_for(event_type: str) -> str:
    mapping: dict[str, str] = {
        "UrlChangeDetected": "url.changed",
        "UrlCrawlFailed": "url.failed",
        "UrlBecameStale": "url.stale",
        "SiteTemplateDriftDetected": "site.drift",
        "ChangeEnriched": "change.enriched",
    }
    return mapping.get(event_type, "url.event")


def _emit_metrics(
    comp: NotifierComposition,
    event_type: str,
    result: HandleEventResult,
    elapsed_seconds: float,
) -> None:
    """Increment the notifier's per-channel-kind Prometheus counters."""
    if comp.metrics is None:
        return
    comp.metrics.task_processed.labels(
        app="notifier",
        outcome=event_type,
    ).inc()
    if result.suppressed:
        return
    comp.metrics.crawl_duration_seconds.labels(app="notifier").observe(elapsed_seconds)
    outcomes: list[NotificationChannelOutcome] = list(getattr(result, "outcomes", []))
    for outcome in outcomes:
        comp.metrics.notification_result.labels(
            app="notifier",
            channel_kind=outcome.channel_kind,
            outcome="success" if outcome.success else "failure",
        ).inc()
    if not outcomes:
        delivered = int(getattr(result, "delivered", 0))
        failed = int(getattr(result, "failed", 0))
        if delivered:
            comp.metrics.notification_result.labels(
                app="notifier",
                channel_kind="unknown",
                outcome="success",
            ).inc(delivered)
        if failed:
            comp.metrics.notification_result.labels(
                app="notifier",
                channel_kind="unknown",
                outcome="failure",
            ).inc(failed)
    skipped = int(getattr(result, "skipped", 0))
    if skipped:
        comp.metrics.notification_result.labels(
            app="notifier",
            channel_kind="unknown",
            outcome="skipped",
        ).inc(skipped)


def _log_dispatch(envelope: EventEnvelope, result: HandleEventResult) -> None:
    if result.suppressed:
        _logger.info(
            "notifier_suppressed",
            event_id=str(envelope.message_id),
            event_type=envelope.type,
            reason=result.suppression_reason or "policy",
        )
        return
    _logger.info(
        "notifier_dispatched",
        event_id=str(envelope.message_id),
        event_type=envelope.type,
        delivered=result.delivered,
        skipped=result.skipped,
        failed=result.failed,
        no_channels=result.no_channels,
    )


def _wire_shutdown_hooks(comp: NotifierComposition) -> None:
    """Register shutdown hooks that stop the consumer and relay cleanly."""
    consumer = comp.consumer
    relay = comp.outbox_relay

    async def _stop_consumer() -> None:
        try:
            await consumer.stop()
        except Exception:
            _logger.warning("notifier_consumer_stop_failed", exc_info=True)

    comp.shutdown.register(_stop_consumer)

    if relay is not None:

        async def _stop_relay() -> None:
            try:
                relay.request_stop()
            except Exception:
                _logger.warning("notifier_relay_stop_failed", exc_info=True)

        comp.shutdown.register(_stop_relay)


async def _run_relay(comp: NotifierComposition) -> asyncio.Task[None] | None:
    """Start the outbox relay as a background task, when configured."""
    relay = comp.outbox_relay
    if relay is None:
        return None
    return asyncio.create_task(relay.run())


async def _run(comp: NotifierComposition, stop: asyncio.Event | None = None) -> None:
    """Run the consumer + outbox relay until the shutdown event fires."""
    handler = _make_handler(comp)
    _wire_shutdown_hooks(comp)
    if stop is None and comp.shutdown is not None:
        comp.shutdown.setup_handlers()
    stop_event = stop if stop is not None else comp.shutdown.shutdown_event
    relay_task = await _run_relay(comp)
    try:
        await comp.consumer.start(handler, prefetch=comp.settings.notifier_prefetch)
    except Exception:
        _logger.exception("notifier_consumer_start_failed")
        if relay_task is not None:
            if comp.outbox_relay is not None:
                comp.outbox_relay.request_stop()
            relay_task.cancel()
            with contextlib.suppress(BaseException):
                await relay_task
        raise
    _logger.info(
        "notifier_started",
        prefetch=comp.settings.notifier_prefetch,
        max_attempts=comp.settings.notify_max_attempts,
        retry_base_seconds=comp.settings.notify_retry_base_seconds,
        per_channel_max_rate=comp.settings.per_channel_max_rate,
    )
    if stop_event is not None:
        await stop_event.wait()
    try:
        await comp.consumer.stop()
    except Exception:
        _logger.warning("notifier_consumer_stop_failed", exc_info=True)
    if relay_task is not None:
        if comp.outbox_relay is not None:
            comp.outbox_relay.request_stop()
        try:
            await relay_task
        except Exception:
            _logger.warning("notifier_relay_join_failed", exc_info=True)


def run() -> None:
    """Module entrypoint: load settings and start the notifier worker.

    Production composition is wired in
    :mod:`lens_notifier.production`. This stub loads settings, configures
    logging, and raises a clear runtime error so the operator sees the
    wiring requirement on a bare ``lens-notifier`` invocation; a
    real composition (e.g. via ``build_production_composition``) is
    used by the deployment artefacts.
    """
    settings = load_settings(NotifierSettings)
    configure_logging(
        level=settings.log_level,
        fmt=settings.log_format,
        force=True,
    )
    raise RuntimeError(
        "lens_notifier.run() requires composition; wire deps via "
        "lens_notifier.production.build_production_composition()",
    )
