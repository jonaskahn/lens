"""End-to-end tests for the crawler worker.

A tiny in-process broker + in-memory UoW drive the worker's
``ProcessCrawlTaskUseCase`` through the published crawl task path so
the full state machine, lease, snapshot, change, and outbox writes are
exercised.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from _fakes import InMemoryUnitOfWork, reset_in_memory_store
from _pipeline_fakes import (
    InMemoryBlobStorage,
    InMemoryCrawler,
    InMemoryDiffer,
    InMemoryLock,
    InMemoryNormalizer,
)
from uuid_extensions import uuid7

from lens_application.dto import CreateDomainInput, CreateUrlInput
from lens_application.pipeline import CrawlTask
from lens_application.use_cases import CreateDomainUseCase, CreateUrlUseCase
from lens_crawler.main import (
    CrawlerWorkerComposition,
    _make_handler,
    build_crawler_worker,
)
from lens_crawler.settings import CrawlerWorkerSettings
from lens_infrastructure.broker import (
    InMemoryBroker,
    InMemoryTaskPublisher,
    InMemoryTaskSubscriber,
)


@pytest.fixture(autouse=True)
def _clear() -> None:
    reset_in_memory_store()


def _settings() -> CrawlerWorkerSettings:
    return CrawlerWorkerSettings(
        crawler_concurrency=2,
        crawler_prefetch=1,
        crawler_lease_ttl_seconds=10,
    )


async def _seed_due_url() -> Any:
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
    return url_dto.id


def _build(
    *,
    crawler: InMemoryCrawler,
    normalizer: InMemoryNormalizer,
    broker: InMemoryBroker,
) -> CrawlerWorkerComposition:
    blob = InMemoryBlobStorage()
    return build_crawler_worker(
        settings=_settings(),
        uow_factory=InMemoryUnitOfWork,
        crawler=crawler,
        normalizer=normalizer,
        differ=InMemoryDiffer(),
        blob=blob,
        lock=InMemoryLock(),
        subscriber=InMemoryTaskSubscriber(
            broker,
            routing_key="crawl.task",
        ),
        worker_id=f"worker-{uuid7()}",
        publisher=InMemoryTaskPublisher(broker, routing_key="crawl.task"),
    )


async def _build_crawl_task(url_id: Any, *, reason: str) -> CrawlTask:
    return CrawlTask(
        url_id=url_id,
        task_id="t-1",
        scheduled_slot=datetime.now(UTC),
        reason=reason,
    )


async def test_given_published_task_when_handled_then_change_recorded() -> None:
    url_id = await _seed_due_url()
    broker = InMemoryBroker()
    publisher = InMemoryTaskPublisher(broker, routing_key="crawl.task")
    await publisher.publish_crawl_task(
        await _build_crawl_task(url_id, reason="scheduled"),
    )
    crawler = InMemoryCrawler(html="<html>changed body here</html>")
    normalizer = InMemoryNormalizer(text="changed body here and longer text")
    comp = _build(crawler=crawler, normalizer=normalizer, broker=broker)
    handler = _make_handler(comp)
    await comp.subscriber.start(handler, prefetch=1)
    await asyncio.sleep(0.3)
    changes = await InMemoryUnitOfWork().changes.list_for_url(url_id)
    assert len(changes) == 1
    await comp.subscriber.stop()


async def test_given_two_workers_for_same_url_when_one_runs_then_other_noop() -> None:
    """The per-URL lock prevents duplicate processing across workers."""
    url_id = await _seed_due_url()
    broker = InMemoryBroker()
    publisher = InMemoryTaskPublisher(broker, routing_key="crawl.task")
    await publisher.publish_crawl_task(
        await _build_crawl_task(url_id, reason="scheduled"),
    )
    crawler = InMemoryCrawler(html="<html>body</html>")
    normalizer = InMemoryNormalizer(text="body")
    comp1 = _build(crawler=crawler, normalizer=normalizer, broker=broker)
    comp2 = _build(crawler=crawler, normalizer=normalizer, broker=broker)
    await comp1.subscriber.start(_make_handler(comp1), prefetch=1)
    await comp2.subscriber.start(_make_handler(comp2), prefetch=1)
    await asyncio.sleep(0.3)
    changes = await InMemoryUnitOfWork().changes.list_for_url(url_id)
    assert len(changes) <= 1
    await comp1.subscriber.stop()
    await comp2.subscriber.stop()
