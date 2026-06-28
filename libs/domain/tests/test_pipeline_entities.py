"""Tests for the Snapshot, Change, and URL state machine domain entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from uuid_extensions import uuid7

from lens_common.errors import DomainError
from lens_domain.entities import Change, Domain, Snapshot, Url
from lens_domain.enums import UrlStatus
from lens_domain.errors import InvalidStateTransition
from lens_domain.ids import (
    ChangeId,
    DomainId,
    SnapshotId,
    UrlId,
)
from lens_domain.value_objects import (
    ContentHash,
    DiffSummary,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
HASH_A = ContentHash(hex="a" * 64)
HASH_B = ContentHash(hex="b" * 64)


def _make_url() -> Url:
    domain = Domain.create(id=DomainId(uuid7()), host="example.com", now=NOW)
    return Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )


def _make_snapshot(*, url: Url, hash_value: ContentHash = HASH_A) -> Snapshot:
    return Snapshot.create(
        id=SnapshotId(uuid7()),
        url_id=url.id_vo,
        content_ref=f"snapshots/{url.id}/x.html.gz",
        content_hash=hash_value,
        http_status=200,
        byte_size=128,
        fetched_at=NOW,
        now=NOW,
    )


def test_given_snapshot_when_empty_content_ref_then_raises() -> None:
    url = _make_url()
    with pytest.raises(DomainError):
        Snapshot.create(
            id=SnapshotId(uuid7()),
            url_id=url.id_vo,
            content_ref="",
            content_hash=HASH_A,
            fetched_at=NOW,
            now=NOW,
        )


def test_given_change_when_hashes_match_then_build_raises() -> None:
    url = _make_url()
    new_snap = _make_snapshot(url=url, hash_value=HASH_A)
    with pytest.raises(DomainError):
        Change.build(
            id=ChangeId(uuid7()),
            url_id=url.id_vo,
            previous_hash=HASH_A,
            new_hash=HASH_A,
            previous_snapshot_id=None,
            new_snapshot_id=new_snap.id_vo,
            diff_summary=DiffSummary(added_count=1, removed_count=0),
            now=NOW,
        )


def test_given_change_when_hashes_differ_then_build_succeeds() -> None:
    url = _make_url()
    new_snap = _make_snapshot(url=url, hash_value=HASH_B)
    change = Change.build(
        id=ChangeId(uuid7()),
        url_id=url.id_vo,
        previous_hash=HASH_A,
        new_hash=HASH_B,
        previous_snapshot_id=None,
        new_snapshot_id=new_snap.id_vo,
        diff_summary=DiffSummary(added_count=2, removed_count=1),
        now=NOW,
    )
    assert change.significant is True
    assert change.diff_summary.added_count == 2


def test_given_url_when_claim_from_idle_then_status_enqueued_and_lease_set() -> None:
    url = _make_url()
    url.claim(worker_id="w-1", lease_ttl=timedelta(seconds=30), now=NOW)
    assert url.status == UrlStatus.ENQUEUED
    assert url.locked_by == "w-1"
    assert url.lock_expires_at == NOW + timedelta(seconds=30)
    assert url.enqueued_at == NOW


def test_given_url_when_claim_from_non_idle_then_raises() -> None:
    url = _make_url()
    url.claim(worker_id="w-1", lease_ttl=timedelta(seconds=30), now=NOW)
    with pytest.raises(InvalidStateTransition):
        url.claim(worker_id="w-2", lease_ttl=timedelta(seconds=30), now=NOW)


def test_given_url_when_start_crawl_from_enqueued_then_crawling() -> None:
    url = _make_url()
    url.claim(worker_id="w-1", lease_ttl=timedelta(seconds=30), now=NOW)
    url.start_crawl(now=NOW)
    assert url.status == UrlStatus.CRAWLING


def test_given_url_when_start_crawl_from_idle_then_raises() -> None:
    url = _make_url()
    with pytest.raises(InvalidStateTransition):
        url.start_crawl(now=NOW)


def test_given_url_when_record_success_with_change_then_returns_event() -> None:
    url = _make_url()
    url.claim(worker_id="w-1", lease_ttl=timedelta(seconds=30), now=NOW)
    url.start_crawl(now=NOW)
    snap = _make_snapshot(url=url, hash_value=HASH_B)
    change = Change.build(
        id=ChangeId(uuid7()),
        url_id=url.id_vo,
        previous_hash=None,
        new_hash=HASH_B,
        previous_snapshot_id=None,
        new_snapshot_id=snap.id_vo,
        diff_summary=DiffSummary(added_count=3, removed_count=0),
        now=NOW,
    )
    event = url.record_success(snapshot=snap, change=change, now=NOW)
    assert event is not None
    assert event.url_id == url.id
    assert event.change_id == change.id
    assert url.status == UrlStatus.IDLE
    assert url.locked_by is None
    assert url.last_hash == HASH_B.hex
    assert url.next_due_at == NOW + timedelta(seconds=600)


def test_given_url_when_record_success_without_change_then_no_event() -> None:
    url = _make_url()
    url.claim(worker_id="w-1", lease_ttl=timedelta(seconds=30), now=NOW)
    url.start_crawl(now=NOW)
    snap = _make_snapshot(url=url, hash_value=HASH_B)
    event = url.record_success(snapshot=snap, change=None, now=NOW)
    assert event is None
    assert url.last_hash == HASH_B.hex
    assert url.consecutive_errors == 0


def test_given_url_when_record_error_then_backoff_and_event_returned() -> None:
    url = _make_url()
    url.claim(worker_id="w-1", lease_ttl=timedelta(seconds=30), now=NOW)
    url.start_crawl(now=NOW)
    event = url.record_error("timeout", event_id=uuid7(), now=NOW)
    assert url.consecutive_errors == 1
    assert url.locked_by is None
    assert event.error == "timeout"
    assert event.consecutive_errors == 1
    assert event.event_id != UUID(int=0)
    assert url.next_due_at > NOW


def test_given_two_urls_when_record_error_then_events_have_distinct_ids() -> None:
    url_a = _make_url()
    url_b = _make_url()
    for url in (url_a, url_b):
        url.claim(worker_id="w-1", lease_ttl=timedelta(seconds=30), now=NOW)
        url.start_crawl(now=NOW)
    eid_a = uuid7()
    eid_b = uuid7()
    event_a = url_a.record_error("timeout", event_id=eid_a, now=NOW)
    event_b = url_b.record_error("timeout", event_id=eid_b, now=NOW)
    assert event_a.event_id == eid_a
    assert event_b.event_id == eid_b
    assert event_a.event_id != event_b.event_id


def test_given_url_when_release_from_enqueued_then_idle() -> None:
    url = _make_url()
    url.claim(worker_id="w-1", lease_ttl=timedelta(seconds=30), now=NOW)
    url.release(now=NOW)
    assert url.status == UrlStatus.IDLE
    assert url.locked_by is None


def test_given_url_when_disable_due_to_errors_then_status_disabled() -> None:
    url = _make_url()
    url.claim(worker_id="w-1", lease_ttl=timedelta(seconds=30), now=NOW)
    url.disable_due_to_errors(now=NOW)
    assert url.status == UrlStatus.DISABLED
    assert url.locked_by is None


def test_given_url_when_mark_due_then_next_due_at_now() -> None:
    url = _make_url()
    later = NOW + timedelta(hours=1)
    url.next_due_at = later
    url.mark_due(now=NOW)
    assert url.next_due_at == NOW
    assert url.status == UrlStatus.IDLE
