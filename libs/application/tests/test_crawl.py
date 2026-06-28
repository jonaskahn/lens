"""Tests for the crawl and diff use cases.

Uses the in-memory UoW + in-memory port fakes so the full
``ProcessCrawlTaskUseCase`` path runs without a database or broker.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from _fakes import InMemoryUnitOfWork, reset_in_memory_store
from _pipeline_fakes import (
    InMemoryBlobStorage,
    InMemoryCrawler,
    InMemoryDiffer,
    InMemoryLock,
    InMemoryNormalizer,
    InMemoryTaskPublisher,
)
from uuid_extensions import uuid7

from lens_application.dto import (
    EnqueueCheckResult,
    TriggerCheckInput,
    TriggerCheckResult,
)
from lens_application.errors import NotFoundError, ValidationFailed
from lens_application.use_cases.crawl import (
    EnqueueDueUrlsUseCase,
    GetChangeDiffUseCase,
    GetLatestSnapshotUseCase,
    ListChangesUseCase,
    ProcessCrawlTaskUseCase,
    TriggerCheckUseCase,
)
from lens_domain.entities import Domain, Url
from lens_domain.enums import UrlStatus
from lens_domain.ids import DomainId, UrlId
from lens_domain.value_objects import (
    CrawlConfig,
    DiffConfig,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clear() -> None:
    reset_in_memory_store()


def _make_url(*, address: str = "https://example.com/p") -> Url:
    domain = Domain.create(id=DomainId(uuid7()), host="example.com", now=NOW)
    return Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address=address,
        interval_seconds=600,
        domain_host=domain.host,
        crawl_config=CrawlConfig(timeout_seconds=10),
        diff_config=DiffConfig(min_text_length=1),
        now=NOW,
    )


async def _new_due_url() -> Url:
    from lens_application.dto import CreateDomainInput, CreateUrlInput
    from lens_application.use_cases import CreateDomainUseCase, CreateUrlUseCase

    domain = await CreateDomainUseCase(_factory).execute(
        CreateDomainInput(host="example.com"),
    )
    # Pin the URL's next_due_at to NOW so the scheduler enqueue picks it up.
    async with _factory() as uow:
        url_dto = await CreateUrlUseCase(_factory).execute(
            CreateUrlInput(
                domain_id=domain.id,
                address="https://example.com/p",
                interval_seconds=600,
            ),
        )
        url_entity = await uow.urls.get(url_dto.id)
        assert url_entity is not None
        url_entity.next_due_at = NOW
        await uow.urls.update(url_entity)
    uow2 = _factory()
    stored = await uow2.urls.get(url_dto.id)
    assert stored is not None
    return stored


def _factory() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


def _build_publisher() -> InMemoryTaskPublisher:
    return InMemoryTaskPublisher()


async def test_given_due_url_when_enqueue_then_publishes_one_task() -> None:
    url = await _new_due_url()
    publisher = _build_publisher()
    use_case = EnqueueDueUrlsUseCase(_factory, publisher)
    result = await use_case.execute({"now": NOW})
    assert isinstance(result, EnqueueCheckResult)
    assert result.enqueued == 1
    assert result.url_ids == [url.id]
    assert len(publisher.published) == 1
    assert publisher.published[0].url_id == url.id
    assert publisher.published[0].reason == "scheduled"


async def test_given_no_due_urls_when_enqueue_then_publishes_nothing() -> None:
    publisher = _build_publisher()
    use_case = EnqueueDueUrlsUseCase(_factory, publisher)
    result = await use_case.execute({"now": NOW})
    assert result.enqueued == 0
    assert publisher.published == []


async def test_given_due_url_when_enqueue_then_url_is_claimed() -> None:
    """Claiming transitions the URL to ``ENQUEUED`` with a lease so a second
    scheduler cannot re-enqueue the same row.

    The ``SELECT ... FOR UPDATE SKIP LOCKED`` half of the multi-instance
    guarantee is provided by the SQLAlchemy repository against Postgres;
    this test pins the in-process half: the use case must persist the
    claim before the UoW commits.
    """
    url = await _new_due_url()
    publisher = _build_publisher()
    use_case = EnqueueDueUrlsUseCase(_factory, publisher)
    result = await use_case.execute({"now": NOW})
    assert result.enqueued == 1

    async with _factory() as uow:
        stored = await uow.urls.get(url.id)
        assert stored is not None
        assert stored.status == UrlStatus.ENQUEUED
        assert stored.locked_by == "scheduler"
        assert stored.lock_expires_at is not None
        assert stored.lock_expires_at > NOW
        assert stored.enqueued_at is not None

    # A second scheduler tick with the same clock must see no due rows.
    second = await use_case.execute({"now": NOW})
    assert second.enqueued == 0
    assert publisher.published == [publisher.published[0]]


async def test_given_url_when_trigger_check_then_publishes_one_task() -> None:
    url = await _new_due_url()
    publisher = _build_publisher()
    use_case = TriggerCheckUseCase(_factory, publisher)
    result = await use_case.execute(TriggerCheckInput(url_id=url.id))
    assert isinstance(result, TriggerCheckResult)
    assert result.enqueued == 1
    assert result.url_ids == [url.id]
    assert publisher.published[0].reason == "manual"


async def test_given_unknown_target_when_trigger_check_then_raises() -> None:
    publisher = _build_publisher()
    use_case = TriggerCheckUseCase(_factory, publisher)
    with pytest.raises(ValidationFailed):
        await use_case.execute(TriggerCheckInput())
    with pytest.raises(NotFoundError):
        await use_case.execute(TriggerCheckInput(url_id=UUID(int=1)))


async def test_given_changed_html_when_process_task_then_change_recorded() -> None:
    url = await _new_due_url()
    blob = InMemoryBlobStorage()
    crawler = InMemoryCrawler(html="<html>changed body here</html>")
    normalizer = InMemoryNormalizer(text="changed body here and longer text")
    differ = InMemoryDiffer()
    lock = InMemoryLock()
    use_case = ProcessCrawlTaskUseCase(
        _factory,
        crawler=crawler,
        normalizer=normalizer,
        differ=differ,
        blob=blob,
        lock=lock,
    )
    result = await use_case.execute({"url_id": url.id})
    assert result["status"] == "change_detected"
    changes = await _factory().changes.list_for_url(url.id)
    assert len(changes) == 1
    snapshots = await _factory().snapshots.list_for_url(url.id)
    assert len(snapshots) == 1
    outbox_rows = await _factory().outbox.list_unsent()
    assert len(outbox_rows) == 1
    assert outbox_rows[0]["event_type"] == "UrlChangeDetected"


async def test_given_unchanged_text_when_process_task_then_skip() -> None:
    url = await _new_due_url()
    blob = InMemoryBlobStorage()
    crawler = InMemoryCrawler()
    normalizer = InMemoryNormalizer(text="x")  # below min_text_length
    differ = InMemoryDiffer()
    lock = InMemoryLock()
    use_case = ProcessCrawlTaskUseCase(
        _factory,
        crawler=crawler,
        normalizer=normalizer,
        differ=differ,
        blob=blob,
        lock=lock,
    )
    result = await use_case.execute({"url_id": url.id})
    assert result["status"] == "skipped"
    changes = await _factory().changes.list_for_url(url.id)
    assert changes == []


async def test_given_same_content_recrawl_when_process_task_then_no_duplicate_snapshot() -> None:
    url = await _new_due_url()
    blob = InMemoryBlobStorage()
    crawler = InMemoryCrawler()
    normalizer = InMemoryNormalizer(text="stable page content that is long enough to pass")
    differ = InMemoryDiffer()
    lock = InMemoryLock()
    use_case = ProcessCrawlTaskUseCase(
        _factory,
        crawler=crawler,
        normalizer=normalizer,
        differ=differ,
        blob=blob,
        lock=lock,
    )
    first = await use_case.execute({"url_id": url.id})
    assert first["status"] == "change_detected"
    async with _factory() as uow:
        stored_url = await uow.urls.get(url.id)
        assert stored_url is not None
        stored_url.last_checked_at = NOW
        stored_url.status = UrlStatus.IDLE
        stored_url.next_due_at = NOW
        await uow.urls.update(stored_url)
    second = await use_case.execute({"url_id": url.id})
    assert second["status"] == "skipped"
    changes = await _factory().changes.list_for_url(url.id)
    assert len(changes) == 1
    snapshots = await _factory().snapshots.list_for_url(url.id)
    assert len(snapshots) == 1
    async with _factory() as uow:
        final_url = await uow.urls.get(url.id)
        assert final_url is not None
        assert final_url.status == UrlStatus.IDLE


async def test_given_lease_held_when_process_task_then_noop() -> None:
    url = await _new_due_url()
    blob = InMemoryBlobStorage()
    crawler = InMemoryCrawler()
    normalizer = InMemoryNormalizer()
    differ = InMemoryDiffer()
    lock = InMemoryLock()
    await lock.acquire(
        f"lens:lock:url:{url.id}",
        ttl_seconds=60,
        token="other",
    )
    use_case = ProcessCrawlTaskUseCase(
        _factory,
        crawler=crawler,
        normalizer=normalizer,
        differ=differ,
        blob=blob,
        lock=lock,
    )
    result = await use_case.execute({"url_id": url.id})
    assert result["status"] == "skipped_locked"
    assert crawler.calls == []


async def test_given_changed_html_when_list_changes_then_returns_dto() -> None:
    url = await _new_due_url()
    blob = InMemoryBlobStorage()
    crawler = InMemoryCrawler()
    normalizer = InMemoryNormalizer(text="brand new content here please")
    differ = InMemoryDiffer()
    lock = InMemoryLock()
    use_case = ProcessCrawlTaskUseCase(
        _factory,
        crawler=crawler,
        normalizer=normalizer,
        differ=differ,
        blob=blob,
        lock=lock,
    )
    await use_case.execute({"url_id": url.id})

    list_use = ListChangesUseCase(_factory)
    result = await list_use.execute({"url_id": url.id})
    assert len(result.items) == 1
    assert result.items[0].url_id == url.id


async def test_given_change_when_get_diff_then_returns_summary() -> None:
    url = await _new_due_url()
    blob = InMemoryBlobStorage()
    crawler = InMemoryCrawler()
    normalizer = InMemoryNormalizer(text="brand new content here please")
    differ = InMemoryDiffer()
    lock = InMemoryLock()
    use_case = ProcessCrawlTaskUseCase(
        _factory,
        crawler=crawler,
        normalizer=normalizer,
        differ=differ,
        blob=blob,
        lock=lock,
    )
    await use_case.execute({"url_id": url.id})

    changes = await _factory().changes.list_for_url(url.id)
    diff_use = GetChangeDiffUseCase(_factory)
    payload = await diff_use.execute(changes[0].id)
    assert payload["id"] == changes[0].id
    assert payload["diff_ref"] is not None
    assert "added_count" in payload["summary"]


async def test_given_change_when_get_latest_snapshot_then_returns_dto() -> None:
    url = await _new_due_url()
    blob = InMemoryBlobStorage()
    crawler = InMemoryCrawler()
    normalizer = InMemoryNormalizer(text="brand new content here please")
    differ = InMemoryDiffer()
    lock = InMemoryLock()
    use_case = ProcessCrawlTaskUseCase(
        _factory,
        crawler=crawler,
        normalizer=normalizer,
        differ=differ,
        blob=blob,
        lock=lock,
    )
    await use_case.execute({"url_id": url.id})

    snap_use = GetLatestSnapshotUseCase(_factory)
    snap = await snap_use.execute(url.id)
    assert snap.url_id == url.id
    assert snap.content_hash
