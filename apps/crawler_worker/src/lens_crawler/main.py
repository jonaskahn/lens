"""Composition root for the crawler worker role.

Wires throttle, idempotency, retry/DLQ, graceful shutdown, bounded
concurrency, and Prometheus metrics into the crawl pipeline. The
worker is a thin runtime over :class:`ProcessCrawlTaskUseCase`: it
deserializes a crawl task, calls the use case, and translates the
returned status into a broker action (ack, requeue with delay, or
retry with exponential backoff).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from lens_application.pipeline import (
    BlobStoragePort,
    CrawlerPort,
    CrawlTask,
    DifferPort,
    HtmlNormalizerPort,
    LockPort,
    TaskPublisherPort,
    TaskSubscriberPort,
)
from lens_application.ports import (
    DeadLetterRepositoryPort,
    IdempotencyPort,
    ThrottlePort,
    UnitOfWork,
)
from lens_application.use_cases import ProcessCrawlTaskUseCase
from lens_common.config import load_settings
from lens_common.lifecycle import GracefulShutdown
from lens_common.logging import configure_logging, get_logger
from lens_common.metrics import MetricFactory, create_metrics
from lens_crawler.settings import CrawlerWorkerSettings

__all__ = [
    "CrawlerWorkerComposition",
    "HandlerDecision",
    "build_crawler_worker",
    "run",
]

_logger = get_logger("lens_crawler")

_ACK_STATUSES: frozenset[str] = frozenset(
    {
        "change_detected",
        "skipped",
        "skipped_duplicate",
        "skipped_locked",
        "missing",
        "not_idle",
        "not_enqueued",
        "sent_to_dlq",
    },
)
_REQUEUE_STATUSES: frozenset[str] = frozenset({"throttled"})
_RETRY_STATUSES: frozenset[str] = frozenset({"error"})


class HandlerDecision(StrEnum):
    """Action a worker handler returns after processing one crawl task."""

    ACK = "ack"
    REQUEUE = "requeue"
    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True, slots=True)
class CrawlerWorkerComposition:
    """Wiring container for the crawler worker role.

    Holds the settings, the crawl-task use case, the broker subscriber,
    the optional retry/throttle collaborators, and the lifecycle
    coordinator. Frozen so callers cannot mutate the wiring after
    construction.
    """

    settings: CrawlerWorkerSettings
    process_task: ProcessCrawlTaskUseCase
    subscriber: TaskSubscriberPort
    worker_id: str
    shutdown: GracefulShutdown
    throttle: ThrottlePort | None = None
    idempotency: IdempotencyPort | None = None
    dlq: DeadLetterRepositoryPort | None = None
    publisher: TaskPublisherPort | None = None
    metrics: MetricFactory | None = None


def build_crawler_worker(
    *,
    settings: CrawlerWorkerSettings,
    uow_factory: Callable[[], UnitOfWork],
    crawler: CrawlerPort,
    normalizer: HtmlNormalizerPort,
    differ: DifferPort,
    blob: BlobStoragePort,
    lock: LockPort,
    subscriber: TaskSubscriberPort,
    worker_id: str,
    throttle: ThrottlePort | None = None,
    idempotency: IdempotencyPort | None = None,
    dlq: DeadLetterRepositoryPort | None = None,
    publisher: TaskPublisherPort | None = None,
    metrics: MetricFactory | None = None,
) -> CrawlerWorkerComposition:
    """Build a :class:`CrawlerWorkerComposition` with the canonical wiring.

    Args:
        settings: Crawler worker configuration.
        uow_factory: Factory that produces a fresh :class:`UnitOfWork`.
        crawler: HTTP fetcher adapter.
        normalizer: HTML normalizer adapter.
        differ: Diff adapter.
        blob: Blob storage adapter.
        lock: Distributed lock for per-URL leases.
        subscriber: Broker consumer for ``crawl.tasks``.
        worker_id: Stable id for this worker (used in metrics + lease).
        throttle: Optional per-domain throttle.
        idempotency: Optional task-level idempotency store.
        dlq: Optional dead-letter repository.
        publisher: Optional publisher used to requeue throttled/errored
            tasks with ``attempt + 1`` and a back-off delay.
        metrics: Optional pre-built :class:`MetricFactory`; one is
            constructed with a private registry when not supplied so
            multiple compositions in one process do not collide on the
            global Prometheus registry.

    Returns:
        A frozen :class:`CrawlerWorkerComposition` ready for the run loop.
    """
    return CrawlerWorkerComposition(
        settings=settings,
        process_task=ProcessCrawlTaskUseCase(
            uow_factory,
            crawler=crawler,
            normalizer=normalizer,
            differ=differ,
            blob=blob,
            lock=lock,
            lease_ttl_seconds=settings.crawler_lease_ttl_seconds,
            worker_id=worker_id,
            throttle=throttle,
            idempotency=idempotency,
            dlq=dlq,
            max_attempts=settings.crawl_max_attempts,
            retry_base_seconds=settings.crawl_retry_base_seconds,
        ),
        subscriber=subscriber,
        worker_id=worker_id,
        shutdown=GracefulShutdown(),
        throttle=throttle,
        idempotency=idempotency,
        dlq=dlq,
        publisher=publisher,
        metrics=metrics or MetricFactory(create_metrics()),
    )


class _Handler(Protocol):
    async def __call__(self, body: dict[str, Any]) -> HandlerDecision: ...


def _status_to_decision(status: str) -> HandlerDecision:
    """Translate a use-case status string into a :class:`HandlerDecision`."""
    if status in _ACK_STATUSES:
        return HandlerDecision.DEAD_LETTER if status == "sent_to_dlq" else HandlerDecision.ACK
    if status in _REQUEUE_STATUSES:
        return HandlerDecision.REQUEUE
    if status in _RETRY_STATUSES:
        return HandlerDecision.RETRY
    return HandlerDecision.ACK


def _retry_delay_seconds(base: float, attempt: int) -> float:
    """Capped exponential back-off with a fixed seed of ``base`` seconds."""
    exponent: int = max(attempt - 1, 0)
    return base * float(2**exponent)


def _make_handler(comp: CrawlerWorkerComposition) -> _Handler:
    async def _handle(body: dict[str, Any]) -> HandlerDecision:
        data = body.get("data", body)
        url_id_str = data.get("url_id")
        if not url_id_str:
            _logger.warning("dropping crawl task with no url_id: %s", body)
            return HandlerDecision.ACK
        task_id = body.get("task_id", data.get("task_id"))
        attempt = int(body.get("attempt", 1))
        url_id = UUID(url_id_str)

        start = time.monotonic()
        metrics = comp.metrics
        if metrics is not None:
            metrics.in_flight.labels(app="crawler").inc()
        try:
            result = await comp.process_task.execute(
                {
                    "url_id": url_id,
                    "task_id": task_id,
                    "attempt": attempt,
                },
            )
            status = result.get("status", "unknown")
            decision = _status_to_decision(status)
            _logger.info(
                "processed crawl task url_id=%s status=%s attempt=%s decision=%s",
                url_id_str,
                status,
                attempt,
                decision.value,
            )
            if metrics is not None:
                elapsed = time.monotonic() - start
                metrics.crawl_duration_seconds.labels(app="crawler").observe(elapsed)
                outcome = "error" if status == "sent_to_dlq" else status
                metrics.task_processed.labels(
                    app="crawler",
                    outcome=outcome,
                ).inc()
            await _apply_decision(comp, decision, body, attempt, status)
            return decision
        except (ValueError, TypeError) as exc:
            _logger.warning(
                "malformed crawl task body url_id=%s: %s",
                url_id_str,
                exc,
            )
            return HandlerDecision.ACK
        except Exception:
            _logger.exception("unhandled error processing crawl task url_id=%s", url_id_str)
            return HandlerDecision.RETRY
        finally:
            if metrics is not None:
                metrics.in_flight.labels(app="crawler").dec()

    return _handle


async def _apply_decision(
    comp: CrawlerWorkerComposition,
    decision: HandlerDecision,
    body: dict[str, Any],
    attempt: int,
    status: str,
) -> None:
    if decision is HandlerDecision.ACK or decision is HandlerDecision.DEAD_LETTER:
        if decision is HandlerDecision.DEAD_LETTER and comp.metrics is not None:
            comp.metrics.dlq_count.labels(queue="crawl.tasks.dlq").inc()
        return
    if comp.publisher is None:
        return
    if decision is HandlerDecision.REQUEUE:
        delay = comp.settings.politeness_min_delay_seconds
    else:
        delay = _retry_delay_seconds(comp.settings.crawl_retry_base_seconds, attempt)
    task = _crawl_task_from_body(body)
    if task is None:
        return
    if delay > 0:
        await asyncio.sleep(delay)
    await comp.publisher.publish_crawl_task(task)
    _logger.info(
        "republished crawl task url_id=%s decision=%s status=%s attempt=%s delay=%.2fs",
        task.url_id,
        decision.value,
        status,
        attempt,
        delay,
    )


def _crawl_task_from_body(body: dict[str, Any]) -> CrawlTask | None:
    data = body.get("data", body)
    url_id_str = data.get("url_id")
    if not url_id_str:
        return None
    from datetime import UTC, datetime

    return CrawlTask(
        url_id=UUID(url_id_str),
        task_id=str(body.get("task_id", data.get("task_id", ""))),
        scheduled_slot=datetime.fromisoformat(
            data.get("scheduled_slot", datetime.now(UTC).isoformat()),
        ),
        reason=str(data.get("reason", "scheduled")),
    )


def _make_semaphore(comp: CrawlerWorkerComposition) -> asyncio.Semaphore:
    return asyncio.Semaphore(comp.settings.crawler_concurrency)


def _wire_shutdown_hooks(comp: CrawlerWorkerComposition) -> None:
    """Register shutdown hooks that stop the subscriber cleanly."""
    subscriber = comp.subscriber
    subscriber_stop: Callable[[], Awaitable[None]] = subscriber.stop

    async def _stop_subscriber() -> None:
        try:
            await subscriber_stop()
        except Exception:
            _logger.warning("subscriber stop failed", exc_info=True)

    comp.shutdown.register(_stop_subscriber)


async def _run(comp: CrawlerWorkerComposition, stop: asyncio.Event | None = None) -> None:
    handler = _make_handler(comp)
    semaphore = _make_semaphore(comp)

    async def _bounded(body: dict[str, Any]) -> None:
        async with semaphore:
            await handler(body)

    _wire_shutdown_hooks(comp)
    if stop is None and comp.shutdown is not None:
        comp.shutdown.setup_handlers()
    stop_event = stop if stop is not None else _shutdown_event(comp)
    await comp.subscriber.start(_bounded, prefetch=comp.settings.crawler_prefetch)
    _logger.info(
        "crawler worker %s started (prefetch=%d, concurrency=%d, max_attempts=%d)",
        comp.worker_id,
        comp.settings.crawler_prefetch,
        comp.settings.crawler_concurrency,
        comp.settings.crawl_max_attempts,
    )
    if stop_event is not None:
        await stop_event.wait()
    await comp.subscriber.stop()


def _shutdown_event(comp: CrawlerWorkerComposition) -> asyncio.Event | None:
    if comp.shutdown is None:
        return None
    return comp.shutdown.shutdown_event


def run() -> None:
    """Module entrypoint: load settings and start consuming."""
    settings = load_settings(CrawlerWorkerSettings)
    configure_logging(level=settings.log_level, fmt=settings.log_format, force=True)
    raise RuntimeError(
        "crawler_worker.run() requires composition; wire deps in main.py",
    )
