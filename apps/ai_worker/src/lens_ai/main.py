"""Composition root for the AI worker role.

Consumes ``ChangeNeedsEnrichment`` tasks from the broker, calls the LLM
via :class:`ChangeClassifierPort`, persists the classification, writes a
weak label, and emits ``ChangeEnriched`` outbox events. The worker
supports capped exponential back-off with jitter, dead-letter routing,
Redis idempotency, graceful shutdown, and Prometheus metrics.

The AI worker needs DB, broker, and optionally Redis for idempotency.
It does NOT need crawl4ai, Playwright, or blob write access.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from lens_ai.settings import AIWorkerSettings
from lens_application.pipeline import ChangeClassifierPort
from lens_application.ports import (
    DeadLetterRepositoryPort,
    IdempotencyPort,
    UnitOfWork,
)
from lens_application.use_cases import EnrichChangeUseCase
from lens_common.config import load_settings
from lens_common.lifecycle import GracefulShutdown
from lens_common.logging import configure_logging, get_logger
from lens_common.metrics import MetricFactory, create_metrics
from lens_common.retry import backoff_sleep_seconds
from lens_infrastructure.ai_classifier import VLLMClassifierAdapter
from lens_infrastructure.broker import RabbitEventConsumer

__all__ = [
    "AIWorkerComposition",
    "build_ai_worker",
    "run",
]

_logger = get_logger("lens_ai")

_NIL_UUID: UUID = UUID(int=0)


@dataclass(frozen=True, slots=True)
class AIWorkerComposition:
    """Wiring container for the AI worker role.

    Holds the settings, the enrichment use case, the broker consumer,
    optional Redis-backed idempotency / DLQ stores, the lifecycle
    coordinator, and Prometheus metrics. Frozen so callers cannot
    mutate the wiring after construction.
    """

    settings: AIWorkerSettings
    enrich_change: EnrichChangeUseCase
    consumer: RabbitEventConsumer
    shutdown: GracefulShutdown
    idempotency: IdempotencyPort | None = None
    dlq: DeadLetterRepositoryPort | None = None
    metrics: MetricFactory | None = None


def build_ai_worker(
    *,
    settings: AIWorkerSettings,
    uow_factory: Callable[[], UnitOfWork],
    classifier: ChangeClassifierPort,
    consumer: RabbitEventConsumer,
    idempotency: IdempotencyPort | None = None,
    dlq: DeadLetterRepositoryPort | None = None,
    metrics: MetricFactory | None = None,
) -> AIWorkerComposition:
    """Build a :class:`AIWorkerComposition` with the canonical wiring.

    Args:
        settings: AI worker configuration (prefetch, retry caps, LLM
            endpoint / model).
        uow_factory: Factory that produces a fresh :class:`UnitOfWork`.
            Repositories are resolved from the UoW at use-case time.
        classifier: LLM-backed :class:`ChangeClassifierPort`.
        consumer: Broker consumer for ``enrich`` exchange /
            ``change.enrich`` routing key.
        idempotency: Optional Redis-backed dedup store (checked before
            every LLM call to avoid duplicate spend).
        dlq: Optional dead-letter repository for ``enrich.tasks.dlq``.
        metrics: Optional pre-built :class:`MetricFactory`; one is
            constructed with a private registry when not supplied so
            multiple compositions in one process do not collide on the
            global Prometheus registry.

    Returns:
        A frozen :class:`AIWorkerComposition` ready for the run loop.
    """
    return AIWorkerComposition(
        settings=settings,
        enrich_change=EnrichChangeUseCase(
            uow_factory,
            classifier=classifier,
        ),
        consumer=consumer,
        shutdown=GracefulShutdown(),
        idempotency=idempotency,
        dlq=dlq,
        metrics=metrics or MetricFactory(create_metrics()),
    )


def _coerce_uuid(value: Any, *, field: str) -> UUID:
    """Coerce an on-the-wire value to :class:`UUID`, falling back to nil."""
    if isinstance(value, UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return UUID(value)
        except ValueError:
            _logger.warning("malformed uuid field=%s value=%r", field, value)
    return _NIL_UUID


def _parse_enrichment_body(body: dict[str, Any]) -> dict[str, Any] | None:
    """Validate the enrichment task envelope and return parsed parameters.

    Returns ``None`` when the body is missing required fields or contains
    unparseable values, so the handler can route the task to the DLQ.
    """
    if not isinstance(body, dict):
        return None
    data = body.get("data", body)
    if not isinstance(data, dict):
        return None
    change_id_str = data.get("change_id")
    url_id_str = data.get("url_id")
    if not change_id_str or not url_id_str:
        _logger.warning("enrichment task missing change_id or url_id")
        return None
    change_id = _coerce_uuid(change_id_str, field="change_id")
    url_id = _coerce_uuid(url_id_str, field="url_id")
    if change_id == _NIL_UUID or url_id == _NIL_UUID:
        _logger.warning(
            "enrichment task unparseable ids change_id=%r url_id=%r",
            change_id_str,
            url_id_str,
        )
        return None
    domain_id = _coerce_uuid(data.get("domain_id", _NIL_UUID), field="domain_id")
    if domain_id == _NIL_UUID:
        _logger.warning("enrichment task missing domain_id")
        return None
    category_id_str = data.get("category_id")
    category_id: UUID | None = None
    if category_id_str:
        category_id = _coerce_uuid(category_id_str, field="category_id")
        if category_id == _NIL_UUID:
            category_id = None

    changed_zones = data.get("changed_zones", [])
    first_zone = changed_zones[0] if isinstance(changed_zones, list) and changed_zones else {}
    if not isinstance(first_zone, dict):
        first_zone = {}

    return {
        "change_id": change_id,
        "url_id": url_id,
        "domain_id": domain_id,
        "category_id": category_id,
        "prev_text": str(first_zone.get("prev_text", "")),
        "curr_text": str(first_zone.get("curr_text", "")),
        "zone_name": str(first_zone.get("zone_name", "")),
        "template_class": data.get("template_class"),
        "escalation_reasons": (
            list(data.get("escalation_reasons", [])) if isinstance(data.get("escalation_reasons"), list) else []
        ),
    }


async def _emit_success_metrics(
    comp: AIWorkerComposition,
    enrichment_status: str,
    enriched_event_emitted: bool,
    classification: dict[str, Any] | None,
    elapsed_ms: int,
) -> None:
    """Record Prometheus metrics for a successful enrichment attempt."""
    metrics = comp.metrics
    if metrics is None:
        return
    metrics.enrichment_duration_ms.labels(app="ai").observe(elapsed_ms)
    outcome = "duplicate" if not enriched_event_emitted else "enriched"
    metrics.task_processed.labels(app="ai", outcome=outcome).inc()
    cls = classification or {}
    change_type = str(cls.get("change_type", "other"))
    metrics.classification_result.labels(app="ai", change_type=change_type).inc()
    if enriched_event_emitted:
        tokens = int(cls.get("tokens_used", 0))
        if tokens > 0:
            metrics.llm_tokens_total.labels(app="ai").inc(tokens)


async def _route_to_dlq(
    comp: AIWorkerComposition,
    body: dict[str, Any],
    *,
    reason: str,
) -> None:
    """Persist a dead-letter entry for a task that is malformed or exhausted retries."""
    message_id = str(body.get("message_id") or body.get("data", {}).get("change_id") or "")
    if comp.dlq is not None:
        await comp.dlq.add(
            queue="enrich.tasks.dlq",
            message_id=message_id,
            body=body,
            error=reason,
        )
    if comp.metrics is not None:
        comp.metrics.dlq_count.labels(queue="enrich.tasks.dlq").inc()
    _logger.warning("enrichment routed to dlq message_id=%s reason=%s", message_id, reason)


async def _persist_failed_status(comp: AIWorkerComposition, change_id: UUID) -> None:
    """Mark the change ``enrichment_status='failed'`` after terminal retries."""
    try:
        factory = comp.enrich_change._uow_factory
        async with factory() as uow:
            await uow.changes.update_enrichment_status(change_id, "failed")
            await uow.commit()
    except Exception:
        _logger.warning(
            "failed to persist enrichment_status=failed for change_id=%s",
            change_id,
            exc_info=True,
        )


def _make_handler(
    comp: AIWorkerComposition,
) -> Callable[[dict[str, Any]], Awaitable[None]]:
    """Build the per-message handler dispatched by the broker consumer.

    Retries the enrichment in-process with capped exponential back-off
    up to ``enrich_max_attempts``. Terminal failures are routed to the
    DLQ and the change is marked ``enrichment_status='failed'``.
    Malformed envelopes are sent to the DLQ immediately.
    """

    async def _handle(body: dict[str, Any]) -> None:
        params = _parse_enrichment_body(body)
        if params is None:
            await _route_to_dlq(comp, body, reason="malformed envelope")
            return

        change_id = params["change_id"]
        change_id_str = str(change_id)
        initial_attempt = max(int(body.get("attempt", 1)), 1)
        max_attempts = comp.settings.enrich_max_attempts
        idempotency_key = f"enrich:{change_id_str}"

        if comp.idempotency is not None:
            seen = await comp.idempotency.is_seen(idempotency_key)
            if seen:
                _logger.info("skipping idempotent duplicate change_id=%s", change_id_str)
                if comp.metrics is not None:
                    comp.metrics.task_processed.labels(app="ai", outcome="skipped_duplicate").inc()
                return
            await comp.idempotency.mark_seen(idempotency_key)

        metrics = comp.metrics

        for attempt in range(initial_attempt, max_attempts + 1):
            if metrics is not None:
                metrics.in_flight.labels(app="ai").inc()
            try:
                start = time.monotonic()
                result = await comp.enrich_change.execute(params)
                elapsed_ms = int((time.monotonic() - start) * 1000)

                await _emit_success_metrics(
                    comp,
                    result.enrichment_status,
                    result.enriched_event_emitted,
                    result.classification,
                    elapsed_ms,
                )

                _logger.info(
                    "enriched change_id=%s status=%s emitted=%s attempt=%d/%d",
                    change_id_str,
                    result.enrichment_status,
                    result.enriched_event_emitted,
                    attempt,
                    max_attempts,
                )
                return
            except Exception as exc:
                _logger.warning(
                    "enrichment attempt failed change_id=%s attempt=%d/%d error=%s",
                    change_id_str,
                    attempt,
                    max_attempts,
                    exc,
                )
                if attempt >= max_attempts:
                    await _route_to_dlq(comp, body, reason=str(exc))
                    await _persist_failed_status(comp, change_id)
                    if metrics is not None:
                        metrics.task_processed.labels(app="ai", outcome="dlq").inc()
                    return
                if metrics is not None:
                    metrics.task_processed.labels(app="ai", outcome="retry").inc()
                delay = backoff_sleep_seconds(
                    attempt,
                    base=comp.settings.enrich_retry_base_seconds,
                )
                if delay > 0:
                    await asyncio.sleep(delay)
            finally:
                if metrics is not None:
                    metrics.in_flight.labels(app="ai").dec()

    return _handle


def _wire_shutdown_hooks(comp: AIWorkerComposition) -> None:
    """Register shutdown hooks to stop the consumer cleanly."""
    consumer = comp.consumer

    async def _stop_consumer() -> None:
        try:
            await consumer.stop()
        except Exception:
            _logger.warning("ai_worker_consumer_stop_failed", exc_info=True)

    comp.shutdown.register(_stop_consumer)


async def _consume_loop(comp: AIWorkerComposition) -> None:
    """Run the consumer until the shutdown event fires."""
    handler = _make_handler(comp)
    _wire_shutdown_hooks(comp)
    comp.shutdown.setup_handlers()

    await comp.consumer.start(handler, prefetch=comp.settings.ai_prefetch)
    _logger.info(
        "ai_worker started prefetch=%d max_attempts=%d retry_base=%.1fs",
        comp.settings.ai_prefetch,
        comp.settings.enrich_max_attempts,
        comp.settings.enrich_retry_base_seconds,
    )
    await comp.shutdown.wait()
    await comp.consumer.stop()


def _build_consumer(settings: AIWorkerSettings) -> RabbitEventConsumer:
    """Build a :class:`RabbitEventConsumer` wired for enrichment tasks.

    Subscribes to the ``enrich`` exchange with routing key
    ``change.enrich`` and a dedicated ``enrich.tasks`` quorum queue.
    """
    assert settings.rabbitmq_url is not None, "rabbitmq_url is required for AI worker"
    return RabbitEventConsumer(
        settings.rabbitmq_url,
        exchange="enrich",
        routing_keys=("change.enrich",),
        queue="enrich.tasks",
        prefetch=settings.ai_prefetch,
    )


def run() -> None:
    """Module entrypoint: load settings, wire production composition, and start consuming.

    Requires ``LENS_DATABASE_URL`` and ``LENS_RABBITMQ_URL``; optionally
    ``LENS_REDIS_URL`` for idempotency/DLQ. LLM settings
    (``LENS_LLM_ENDPOINT``, ``LENS_LLM_MODEL``, ``LENS_LLM_TIMEOUT_SECONDS``)
    drive :class:`VLLMClassifierAdapter`.
    """
    import asyncio as _asyncio

    from sqlalchemy.engine import Engine

    from lens_infrastructure.db.base import create_engine_for_url
    from lens_infrastructure.db.unit_of_work import sqlalchemy_uow_factory
    from lens_infrastructure.dead_letter import RedisDeadLetterStore
    from lens_infrastructure.idempotency import RedisIdempotencyStore

    settings = load_settings(AIWorkerSettings)
    configure_logging(
        level=settings.log_level,
        fmt=settings.log_format,
        force=True,
    )

    if not settings.database_url or not settings.rabbitmq_url:
        raise RuntimeError(
            "LENS_DATABASE_URL and LENS_RABBITMQ_URL are required for the AI worker",
        )

    engine: Engine = create_engine_for_url(settings.database_url)

    classifier = VLLMClassifierAdapter(
        base_url=settings.llm_endpoint,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )

    idempotency: IdempotencyPort | None = None
    dlq: DeadLetterRepositoryPort | None = None
    if settings.redis_url is not None:
        try:
            import redis.asyncio as aioredis
        except ImportError:
            aioredis = None  # type: ignore[assignment]
        if aioredis is not None:
            redis_client = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            idempotency = RedisIdempotencyStore(redis_client)
            dlq = RedisDeadLetterStore(redis_client)

    composition = build_ai_worker(
        settings=settings,
        uow_factory=sqlalchemy_uow_factory(engine),
        classifier=classifier,
        consumer=_build_consumer(settings),
        idempotency=idempotency,
        dlq=dlq,
    )

    _asyncio.run(_consume_loop(composition))
