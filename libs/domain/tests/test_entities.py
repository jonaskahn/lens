"""Entity factories, invariants, and state operations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from uuid_extensions import uuid7

from lens_common.errors import DomainError
from lens_domain.entities import (
    Category,
    Change,
    Channel,
    ChannelBinding,
    Domain,
    SiteProfile,
    Snapshot,
    Url,
)
from lens_domain.enums import BindingScope, ChannelKind, UrlStatus
from lens_domain.errors import (
    DuplicateCategory,
    HostMismatch,
    InvalidInterval,
    InvalidScope,
    InvalidStateTransition,
)
from lens_domain.ids import (
    CategoryId,
    ChangeId,
    DomainId,
    ProfileId,
    SnapshotId,
    UrlId,
)
from lens_domain.value_objects import (
    Address,
    ContentHash,
    CrawlConfig,
    DiffConfig,
    DiffSummary,
    Interval,
    NotificationRouting,
    Politeness,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _make_domain(host: str = "example.com") -> Domain:
    return Domain.create(
        id=DomainId(uuid7()),
        host=host,
        display_name="Example",
        now=NOW,
    )


def _make_category(domain: Domain, name: str = "products") -> Category:
    return Category.create(
        id=CategoryId(uuid7()),
        domain_id=domain.id_vo,
        name=name,
        now=NOW,
    )


def test_given_host_with_case_when_create_domain_then_normalised() -> None:
    d = Domain.create(id=DomainId(uuid7()), host="EXAMPLE.com", now=NOW)
    assert d.host.value == "example.com"


def test_given_url_when_host_does_not_match_domain_then_host_mismatch() -> None:
    domain = _make_domain("example.com")
    with pytest.raises(HostMismatch):
        Url.create(
            id=UrlId(uuid7()),
            domain_id=domain.id_vo,
            address="https://other.com/x",
            interval_seconds=600,
            domain_host=domain.host,
            now=NOW,
        )


def test_given_url_when_interval_below_floor_then_raises() -> None:
    domain = _make_domain()
    with pytest.raises(InvalidInterval):
        Url.create(
            id=UrlId(uuid7()),
            domain_id=domain.id_vo,
            address="https://example.com/p",
            interval_seconds=10,
            domain_host=domain.host,
            now=NOW,
        )


def test_given_url_when_created_then_initial_state_is_idle_due_now() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    assert url.status == UrlStatus.IDLE
    assert url.next_due_at == NOW
    assert url.consecutive_errors == 0


def test_given_url_when_update_interval_below_floor_then_raises() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    with pytest.raises(InvalidInterval):
        url.update(interval_seconds=10, now=NOW)


def test_given_category_when_empty_name_then_raises() -> None:
    domain = _make_domain()
    with pytest.raises(DuplicateCategory):
        Category.create(
            id=CategoryId(uuid7()),
            domain_id=domain.id_vo,
            name="   ",
            now=NOW,
        )


def test_given_domain_when_change_host_then_updated() -> None:
    d = _make_domain("old.example.com")
    d.change_host("New.Example.com", now=NOW)
    assert d.host.value == "new.example.com"


def test_given_url_when_lease_held_by_self_then_is_lease_held() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    url.locked_by = "worker-1"
    url.lock_expires_at = NOW.replace(year=2027)
    assert url.is_lease_held("worker-1", NOW) is True
    assert url.is_lease_held("worker-2", NOW) is False
    assert url.lease_is_expired(NOW) is False


def test_given_channel_when_empty_url_then_raises() -> None:
    with pytest.raises(DomainError):
        Channel.create(
            id=uuid7(),
            name="ops",
            kind=ChannelKind.SLACK,
            apprise_url="   ",
            now=NOW,
        )


def test_given_binding_when_global_with_scope_id_then_raises() -> None:
    with pytest.raises(InvalidScope):
        ChannelBinding.create(
            id=uuid7(),
            channel_id=uuid7(),
            scope=BindingScope.GLOBAL,
            scope_id=uuid7(),
            now=NOW,
        )


def test_given_binding_when_domain_without_scope_id_then_raises() -> None:
    with pytest.raises(InvalidScope):
        ChannelBinding.create(
            id=uuid7(),
            channel_id=uuid7(),
            scope=BindingScope.DOMAIN,
            scope_id=None,
            now=NOW,
        )


def test_given_binding_when_valid_then_stores_flags() -> None:
    b = ChannelBinding.create(
        id=uuid7(),
        channel_id=uuid7(),
        scope=BindingScope.DOMAIN,
        scope_id=uuid7(),
        on_change=True,
        on_error=True,
        on_no_change=False,
        now=NOW,
    )
    assert b.on_change is True
    assert b.on_error is True
    assert b.on_no_change is False


def test_binding_update_changes_flags() -> None:
    b = ChannelBinding.create(
        id=uuid7(),
        channel_id=uuid7(),
        scope=BindingScope.URL,
        scope_id=uuid7(),
        on_change=True,
        now=NOW,
    )
    b.update(on_change=False, on_error=True, on_no_change=True)
    assert b.on_change is False
    assert b.on_error is True
    assert b.on_no_change is True


def test_binding_update_partial() -> None:
    b = ChannelBinding.create(
        id=uuid7(),
        channel_id=uuid7(),
        scope=BindingScope.URL,
        scope_id=uuid7(),
        on_change=True,
        on_error=False,
        now=NOW,
    )
    b.update(on_error=True)
    assert b.on_change is True
    assert b.on_error is True
    assert b.on_no_change is False


def test_category_update_all_fields() -> None:
    domain = _make_domain()
    cat = _make_category(domain)
    cat.update(
        name="updated",
        description="new desc",
        crawl_config=CrawlConfig(selector=".x"),
        diff_config=DiffConfig(min_text_length=20),
        routing=NotificationRouting(channel_ids=["ch1"]),
        now=NOW,
    )
    assert cat.name == "updated"
    assert cat.description == "new desc"
    assert cat.crawl_config.selector == ".x"
    assert cat.diff_config.min_text_length == 20


def test_category_update_empty_name_raises() -> None:
    domain = _make_domain()
    cat = _make_category(domain)
    with pytest.raises(DuplicateCategory):
        cat.update(name="   ", now=NOW)


def test_channel_update_all_fields() -> None:
    ch = Channel.create(
        id=uuid7(),
        name="ops",
        kind=ChannelKind.SLACK,
        apprise_url="slack://token",
        now=NOW,
    )
    ch.update(
        name="new-ops",
        kind=ChannelKind.EMAIL,
        apprise_url="mailto:test@test.com",
        enabled=False,
        now=NOW,
    )
    assert ch.name == "new-ops"
    assert ch.kind == ChannelKind.EMAIL
    assert ch.enabled is False


def test_channel_update_empty_name_raises() -> None:
    ch = Channel.create(
        id=uuid7(),
        name="ops",
        kind=ChannelKind.SLACK,
        apprise_url="slack://token",
        now=NOW,
    )
    with pytest.raises(DomainError):
        ch.update(name="   ", now=NOW)


def test_channel_update_empty_url_raises() -> None:
    ch = Channel.create(
        id=uuid7(),
        name="ops",
        kind=ChannelKind.SLACK,
        apprise_url="slack://token",
        now=NOW,
    )
    with pytest.raises(DomainError):
        ch.update(apprise_url="   ", now=NOW)


def test_url_claim_and_start_crawl() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    from datetime import timedelta

    url.claim("w1", timedelta(seconds=60), now=NOW)
    assert url.status == UrlStatus.ENQUEUED
    assert url.locked_by == "w1"

    url.start_crawl(now=NOW)
    assert url.status == UrlStatus.CRAWLING


def test_url_claim_from_non_idle_raises() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    from datetime import timedelta

    url.claim("w1", timedelta(seconds=60), now=NOW)
    with pytest.raises(InvalidStateTransition):
        url.claim("w2", timedelta(seconds=60), now=NOW)


def test_url_start_crawl_from_non_enqueued_raises() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    with pytest.raises(InvalidStateTransition):
        url.start_crawl(now=NOW)


def test_url_record_success_no_change() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    from datetime import timedelta

    url.claim("w1", timedelta(seconds=60), now=NOW)
    url.start_crawl(now=NOW)

    snapshot = Snapshot.create(
        id=SnapshotId(uuid7()),
        url_id=url.id_vo,
        content_ref="s3://bucket/key",
        content_hash=ContentHash(hex="a" * 64),
        fetched_at=NOW,
        now=NOW,
    )
    event = url.record_success(snapshot=snapshot, change=None, now=NOW)
    assert event is None
    assert url.status == UrlStatus.IDLE
    assert url.locked_by is None
    assert url.consecutive_errors == 0


def test_url_record_success_with_change() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    from datetime import timedelta

    url.claim("w1", timedelta(seconds=60), now=NOW)
    url.start_crawl(now=NOW)

    snapshot = Snapshot.create(
        id=SnapshotId(uuid7()),
        url_id=url.id_vo,
        content_ref="s3://bucket/key",
        content_hash=ContentHash(hex="a" * 64),
        fetched_at=NOW,
        now=NOW,
    )
    change = Change.create(
        id=ChangeId(uuid7()),
        url_id=url.id_vo,
        new_snapshot_id=snapshot.id_vo,
        diff_summary=DiffSummary(added_count=5, removed_count=2),
        now=NOW,
    )
    event = url.record_success(snapshot=snapshot, change=change, now=NOW)
    assert event is not None
    assert event.url_id == url.id
    assert event.significant is True


def test_url_record_error() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    from datetime import timedelta

    url.claim("w1", timedelta(seconds=60), now=NOW)
    url.start_crawl(now=NOW)

    event = url.record_error("timeout", event_id=uuid7(), now=NOW)
    assert event.error == "timeout"
    assert event.consecutive_errors == 1
    assert url.status == UrlStatus.IDLE
    assert url.locked_by is None


def test_url_release_from_enqueued() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    from datetime import timedelta

    url.claim("w1", timedelta(seconds=60), now=NOW)
    url.release(now=NOW)
    assert url.status == UrlStatus.IDLE
    assert url.locked_by is None


def test_url_disable_due_to_errors() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    url.disable_due_to_errors(now=NOW)
    assert url.status == UrlStatus.DISABLED
    assert url.locked_by is None


def test_url_mark_due() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    future = NOW.replace(year=2027)
    url.next_due_at = future
    url.mark_due(now=NOW)
    assert url.status == UrlStatus.IDLE
    assert url.next_due_at == NOW


def test_url_lease_is_expired() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    url.locked_by = "w1"
    url.lock_expires_at = NOW.replace(year=2020)
    assert url.lease_is_expired(NOW) is True


def test_site_profile_bootstrap() -> None:
    profile = SiteProfile.bootstrap(
        id=ProfileId(uuid7()),
        domain="example.com",
        url_pattern="/p/**",
        now=NOW,
    )
    assert profile.domain == "example.com"
    assert profile.url_pattern == "/p/**"
    assert profile.version == 1
    assert len(profile.zone_selectors) > 0


def test_site_profile_get_zone() -> None:
    profile = SiteProfile.bootstrap(
        id=ProfileId(uuid7()),
        domain="example.com",
        url_pattern="/p/**",
        now=NOW,
    )
    zone = profile.get_zone("navigation")
    assert zone is not None
    assert zone.name == "navigation"
    assert profile.get_zone("nonexistent") is None


def test_site_profile_with_new_skeleton() -> None:
    profile = SiteProfile.bootstrap(
        id=ProfileId(uuid7()),
        domain="example.com",
        url_pattern="/p/**",
        now=NOW,
    )
    new_profile = profile.with_new_skeleton("abc123", now=NOW)
    assert new_profile.version == 2
    assert new_profile.template_hash == "abc123"


def test_site_profile_empty_domain_raises() -> None:
    with pytest.raises(DomainError):
        SiteProfile.bootstrap(
            id=ProfileId(uuid7()),
            domain="",
            url_pattern="/p/**",
            now=NOW,
        )


def test_site_profile_empty_url_pattern_raises() -> None:
    with pytest.raises(DomainError):
        SiteProfile.bootstrap(
            id=ProfileId(uuid7()),
            domain="example.com",
            url_pattern="",
            now=NOW,
        )


def test_entity_eq_hash_repr() -> None:
    from lens_domain.entities import _Entity

    class MyEntity(_Entity):
        pass

    e1 = MyEntity(uuid7())
    e2 = MyEntity(uuid7())
    assert e1 != e2
    assert hash(e1) != hash(e2)
    assert "MyEntity" in repr(e1)


def test_domain_create_with_overrides() -> None:
    d = Domain.create(
        id=DomainId(uuid7()),
        host="example.com",
        default_crawl_config=CrawlConfig(timeout_seconds=60),
        default_diff_config=DiffConfig(min_text_length=30),
        politeness=Politeness(max_concurrency=5),
        default_routing=NotificationRouting(channel_ids=["ch1"]),
        enabled=False,
        now=NOW,
    )
    assert d.default_crawl_config.timeout_seconds == 60
    assert d.default_diff_config.min_text_length == 30
    assert d.politeness.max_concurrency == 5
    assert d.default_routing.channel_ids == ["ch1"]
    assert d.enabled is False


def test_domain_update_all_fields() -> None:
    d = _make_domain()
    d.update(
        display_name="Updated",
        enabled=False,
        default_crawl_config=CrawlConfig(timeout_seconds=120),
        default_diff_config=DiffConfig(min_text_length=40),
        politeness=Politeness(max_concurrency=3),
        default_routing=NotificationRouting(channel_ids=["ch2"]),
        now=NOW,
    )
    assert d.display_name == "Updated"
    assert d.enabled is False
    assert d.default_crawl_config.timeout_seconds == 120
    assert d.default_diff_config.min_text_length == 40
    assert d.politeness.max_concurrency == 3
    assert d.default_routing.channel_ids == ["ch2"]


def test_domain_update_none_keeps_existing() -> None:
    d = _make_domain()
    orig_crawl = d.default_crawl_config
    d.update(now=NOW)
    assert d.default_crawl_config is orig_crawl


def test_url_update_all_fields() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    url.update(
        enabled=False,
        interval_seconds=3600,
        crawl_config=CrawlConfig(selector=".new"),
        diff_config=DiffConfig(min_text_length=100),
        routing=NotificationRouting(channel_ids=["ch3"]),
        global_min_interval=300,
        now=NOW,
    )
    assert url.enabled is False
    assert url.interval.seconds == 3600
    assert url.crawl_config.selector == ".new"
    assert url.diff_config.min_text_length == 100
    assert url.routing.channel_ids == ["ch3"]


def test_change_build() -> None:
    c = Change.build(
        id=ChangeId(uuid7()),
        url_id=UrlId(uuid7()),
        previous_hash=ContentHash(hex="a" * 64),
        new_hash=ContentHash(hex="b" * 64),
        previous_snapshot_id=SnapshotId(uuid7()),
        new_snapshot_id=SnapshotId(uuid7()),
        diff_summary=DiffSummary(added_count=1),
        diff_ref="ref123",
        semantic_score=0.5,
        now=NOW,
    )
    assert c.diff_summary.added_count == 1
    assert c.semantic_score == 0.5
    assert c.diff_ref == "ref123"


def test_change_build_same_hash_raises() -> None:
    h = ContentHash(hex="a" * 64)
    with pytest.raises(DomainError):
        Change.build(
            id=ChangeId(uuid7()),
            url_id=UrlId(uuid7()),
            previous_hash=h,
            new_hash=h,
            previous_snapshot_id=SnapshotId(uuid7()),
            new_snapshot_id=SnapshotId(uuid7()),
            diff_summary=DiffSummary(),
            now=NOW,
        )


def test_change_requires_diff_summary() -> None:
    with pytest.raises(DomainError):
        Change(
            id=ChangeId(uuid7()),
            url_id=UrlId(uuid7()),
            new_snapshot_id=SnapshotId(uuid7()),
            diff_summary="not-a-diff-summary",  # type: ignore[arg-type]
            created_at=NOW,
        )


def test_url_consecutive_errors_negative_raises() -> None:
    domain = _make_domain()
    with pytest.raises(DomainError):
        Url(
            id=UrlId(uuid7()),
            domain_id=domain.id_vo,
            address=Address(value="https://example.com/p"),
            interval=Interval(seconds=600, global_minimum=300),
            next_due_at=NOW,
            created_at=NOW,
            updated_at=NOW,
            consecutive_errors=-1,
        )


def test_channel_create_empty_name_raises() -> None:
    with pytest.raises(DomainError):
        Channel.create(
            id=uuid7(),
            name="   ",
            kind=ChannelKind.EMAIL,
            apprise_url="mailto:test@test.com",
            now=NOW,
        )


def test_snapshot_create() -> None:
    s = Snapshot.create(
        id=SnapshotId(uuid7()),
        url_id=UrlId(uuid7()),
        content_ref="s3://bucket/key",
        content_hash=ContentHash(hex="a" * 64),
        http_status=200,
        byte_size=1024,
        fetched_at=NOW,
        now=NOW,
    )
    assert s.content_ref == "s3://bucket/key"
    assert s.http_status == 200
    assert s.byte_size == 1024


def test_snapshot_empty_content_ref_raises() -> None:
    with pytest.raises(DomainError):
        Snapshot.create(
            id=SnapshotId(uuid7()),
            url_id=UrlId(uuid7()),
            content_ref="",
            content_hash=ContentHash(hex="a" * 64),
            fetched_at=NOW,
            now=NOW,
        )


def test_url_record_success_from_wrong_state_raises() -> None:
    domain = _make_domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    snapshot = Snapshot.create(
        id=SnapshotId(uuid7()),
        url_id=url.id_vo,
        content_ref="s3://bucket/key",
        content_hash=ContentHash(hex="a" * 64),
        fetched_at=NOW,
        now=NOW,
    )
    with pytest.raises(InvalidStateTransition):
        url.record_success(snapshot=snapshot, change=None, now=NOW)
