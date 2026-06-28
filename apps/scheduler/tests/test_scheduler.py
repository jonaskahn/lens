"""Tests for the scheduler's tick loop and composition root."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from _fakes import InMemoryUnitOfWork, reset_in_memory_store

from lens_application.dto import CreateDomainInput, CreateUrlInput
from lens_application.use_cases import CreateDomainUseCase, CreateUrlUseCase
from lens_infrastructure.broker import InMemoryBroker, InMemoryTaskPublisher
from lens_scheduler.main import (
    SchedulerComposition,
    _run_forever,
    _tick,
    build_scheduler,
)
from lens_scheduler.settings import SchedulerSettings


@pytest.fixture(autouse=True)
def _clear() -> None:
    reset_in_memory_store()


def _settings() -> SchedulerSettings:
    return SchedulerSettings(
        scheduler_tick_seconds=0.1,
        scheduler_batch_size=10,
    )


async def _seed_due_url() -> None:
    factory = InMemoryUnitOfWork
    domain = await CreateDomainUseCase(factory).execute(
        CreateDomainInput(host="example.com"),
    )
    async with factory() as uow:
        url_dto = await CreateUrlUseCase(factory).execute(
            CreateUrlInput(
                domain_id=domain.id,
                address="https://example.com/p",
                interval_seconds=600,
            ),
        )
        url_entity = await uow.urls.get(url_dto.id)
        assert url_entity is not None
        url_entity.next_due_at = datetime.now(UTC)
        await uow.urls.update(url_entity)


def _composition() -> tuple[SchedulerComposition, InMemoryBroker]:
    broker = InMemoryBroker()
    publisher = InMemoryTaskPublisher(broker)
    comp = build_scheduler(
        settings=_settings(),
        uow_factory=InMemoryUnitOfWork,
        publisher=publisher,
    )
    return comp, broker


async def test_given_due_url_when_tick_then_one_task_published() -> None:
    await _seed_due_url()
    comp, broker = _composition()
    enqueued = await _tick(comp)
    assert enqueued == 1
    queue = broker.attach_consumer("crawl.task")
    assert queue.qsize() == 1


async def test_given_no_due_url_when_tick_then_no_task() -> None:
    comp, broker = _composition()
    enqueued = await _tick(comp)
    assert enqueued == 0
    queue = broker.attach_consumer("crawl.task")
    assert queue.qsize() == 0


async def test_given_already_enqueued_when_tick_then_no_double_publish() -> None:
    await _seed_due_url()
    comp, broker = _composition()
    await _tick(comp)
    # After the first tick the URL is in ENQUEUED, so a second tick should
    # not re-publish until the worker transitions it back to IDLE.
    enqueued = await _tick(comp)
    assert enqueued == 0
    queue = broker.attach_consumer("crawl.task")
    assert queue.qsize() == 1


async def test_given_run_loop_when_stop_event_set_then_exits() -> None:
    await _seed_due_url()
    comp, _ = _composition()
    stop = asyncio.Event()
    stop.set()
    await _run_forever(comp, stop)
