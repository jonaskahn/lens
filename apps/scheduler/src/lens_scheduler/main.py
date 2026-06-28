"""Composition root for the scheduler role.

Supports leader election (Redis lock), hash-based sharding,
backpressure via queue-depth probe, per-domain fairness, and
tick-level Prometheus metrics.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass

from lens_application.pipeline import LockPort, TaskPublisherPort
from lens_application.ports import UnitOfWork
from lens_application.use_cases import EnqueueDueUrlsUseCase
from lens_common.config import load_settings
from lens_common.lifecycle import GracefulShutdown
from lens_common.logging import configure_logging, get_logger
from lens_common.metrics import MetricFactory, create_metrics
from lens_scheduler.settings import SchedulerSettings

__all__ = ["SchedulerComposition", "build_scheduler", "run"]

_logger = get_logger("lens_scheduler")


@dataclass(frozen=True, slots=True)
class SchedulerComposition:
    """Wiring container for the scheduler role.

    Holds the settings, the enqueue use case, and optional runtime
    collaborators (leader lock, graceful-shutdown coordinator, metrics).
    Frozen so callers cannot mutate the wiring after construction.
    """

    settings: SchedulerSettings
    enqueue_due_urls: EnqueueDueUrlsUseCase
    leader_lock: LockPort | None = None
    shutdown: GracefulShutdown | None = None
    metrics: MetricFactory | None = None


def build_scheduler(
    *,
    settings: SchedulerSettings,
    uow_factory: Callable[[], UnitOfWork],
    publisher: TaskPublisherPort,
    leader_lock: LockPort | None = None,
    metrics: MetricFactory | None = None,
) -> SchedulerComposition:
    """Build a :class:`SchedulerComposition` with the canonical wiring.

    Args:
        settings: Scheduler configuration (intervals, sharding, etc.).
        uow_factory: Factory that produces a fresh :class:`UnitOfWork`.
        publisher: Broker publisher for crawl tasks.
        leader_lock: Optional distributed lock for leader election.
        metrics: Optional pre-built :class:`MetricFactory`; one is
            constructed with a private registry when not supplied so
            multiple compositions in one process do not collide on the
            global Prometheus registry.

    Returns:
        A frozen :class:`SchedulerComposition` ready for the tick loop.
    """
    return SchedulerComposition(
        settings=settings,
        enqueue_due_urls=EnqueueDueUrlsUseCase(
            uow_factory,
            publisher,
            batch_size=settings.scheduler_batch_size,
        ),
        leader_lock=leader_lock,
        shutdown=GracefulShutdown(),
        metrics=metrics or MetricFactory(create_metrics()),
    )


async def _acquire_leader(comp: SchedulerComposition) -> str | None:
    if comp.leader_lock is None:
        return "noop"
    token = f"scheduler-{comp.settings.shard_id}"
    result = await comp.leader_lock.acquire(
        key=comp.settings.leader_lock_key,
        ttl_seconds=int(comp.settings.scheduler_tick_seconds * 3),
        token=token,
    )
    return result if result else None


async def _release_leader(comp: SchedulerComposition, token: str | None) -> None:
    if comp.leader_lock is not None and token is not None and token != "noop":
        await comp.leader_lock.release(
            comp.settings.leader_lock_key,
            token,
        )


async def _tick(comp: SchedulerComposition) -> int:
    tick_start = time.monotonic()
    result = await comp.enqueue_due_urls.execute(
        {
            "max_queue_depth": comp.settings.max_queue_depth,
            "shard_id": comp.settings.shard_id,
            "shard_count": comp.settings.shard_count,
        },
    )
    elapsed = time.monotonic() - tick_start
    if comp.metrics is not None:
        comp.metrics.tick_duration_seconds.labels(app="scheduler").observe(elapsed)
        comp.metrics.task_processed.labels(app="scheduler", outcome="enqueued").inc(
            result.enqueued,
        )
    if result.enqueued:
        _logger.info("scheduler tick: enqueued %d urls in %.2fs", result.enqueued, elapsed)
    return result.enqueued


async def _wait_or_timeout(stop_event: asyncio.Event, timeout: float) -> None:
    """Wait for ``stop_event`` or ``timeout`` seconds, whichever comes first."""
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stop_event.wait(), timeout=timeout)


async def _run_forever(comp: SchedulerComposition, stop: asyncio.Event | None = None) -> None:
    interval = comp.settings.scheduler_tick_seconds
    stop_event = stop if stop is not None else _shutdown_event(comp)
    if stop is None and comp.shutdown is not None:
        comp.shutdown.setup_handlers()
    while stop_event is None or not stop_event.is_set():
        leader_token = await _acquire_leader(comp)
        if leader_token is None:
            if stop_event is None:
                await asyncio.sleep(interval)
            else:
                await _wait_or_timeout(stop_event, interval)
            continue
        try:
            await _tick(comp)
        except Exception:
            _logger.exception("scheduler tick failed; continuing")
        finally:
            await _release_leader(comp, leader_token)
        if stop_event is None or stop_event.is_set():
            break
        await _wait_or_timeout(stop_event, interval)


def _shutdown_event(comp: SchedulerComposition) -> asyncio.Event | None:
    if comp.shutdown is None:
        return None
    return comp.shutdown.shutdown_event


def run() -> None:
    """Module entrypoint: load settings and start the tick loop."""
    settings = load_settings(SchedulerSettings)
    configure_logging(level=settings.log_level, fmt=settings.log_format, force=True)
    raise RuntimeError(
        "scheduler.run() requires a UoW factory + publisher; "
        "wire them at composition time (see apps/scheduler/main.py)",
    )
