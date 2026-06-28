"""SQLAlchemy mapping tests for snapshots / changes / outbox."""

from __future__ import annotations

from datetime import UTC, datetime

from uuid_extensions import uuid7

from lens_domain.entities import Change, Domain, Snapshot, Url
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
from lens_infrastructure.db.mapping import (
    change_from_model,
    change_to_model,
    outbox_from_model,
    outbox_to_model,
    snapshot_from_model,
    snapshot_to_model,
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


def test_given_snapshot_when_round_tripped_then_fields_match() -> None:
    url = _make_url()
    snap = Snapshot.create(
        id=SnapshotId(uuid7()),
        url_id=url.id_vo,
        content_ref="snapshots/abc.html.gz",
        content_hash=HASH_A,
        http_status=200,
        byte_size=1024,
        fetched_at=NOW,
        now=NOW,
    )
    model = snapshot_to_model(snap)
    restored = snapshot_from_model(model)
    assert restored.id == snap.id
    assert restored.content_hash.hex == HASH_A.hex
    assert restored.http_status == 200
    assert restored.byte_size == 1024


def test_given_change_when_round_tripped_then_summary_matches() -> None:
    url = _make_url()
    new_snap = Snapshot.create(
        id=SnapshotId(uuid7()),
        url_id=url.id_vo,
        content_ref="snapshots/new.html.gz",
        content_hash=HASH_B,
        fetched_at=NOW,
        now=NOW,
    )
    change = Change.build(
        id=ChangeId(uuid7()),
        url_id=url.id_vo,
        previous_hash=HASH_A,
        new_hash=HASH_B,
        previous_snapshot_id=None,
        new_snapshot_id=new_snap.id_vo,
        diff_summary=DiffSummary(added_count=4, removed_count=2),
        semantic_score=0.42,
        significant=True,
        now=NOW,
    )
    model = change_to_model(change)
    assert model.added_count == 4
    assert model.removed_count == 2
    assert model.semantic_score == 0.42
    restored = change_from_model(model)
    assert restored.diff_summary.added_count == 4
    assert restored.significant is True


def test_given_outbox_row_when_round_tripped_then_payload_preserved() -> None:
    event_id = uuid7()
    payload = {"url_id": str(uuid7()), "foo": "bar"}
    model = outbox_to_model(
        id=uuid7(),
        aggregate_type="url",
        aggregate_id=uuid7(),
        event_type="UrlChangeDetected",
        event_id=event_id,
        payload=payload,
        created_at=NOW,
    )
    restored = outbox_from_model(model)
    assert restored["event_id"] == event_id
    assert restored["event_type"] == "UrlChangeDetected"
    assert restored["payload"] == payload
