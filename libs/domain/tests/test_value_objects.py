"""Value object invariants and validation."""

from __future__ import annotations

import pytest

from lens_common.errors import DomainError
from lens_domain.enums import SignificanceRuleType, TriggerType
from lens_domain.errors import InvalidAddress, InvalidInterval, InvalidPoliteness
from lens_domain.value_objects import (
    Address,
    ContentHash,
    CrawlConfig,
    DiffConfig,
    DiffSummary,
    Hostname,
    Interval,
    NotificationRouting,
    Politeness,
    SignificanceRule,
)


def test_given_valid_hostname_when_constructed_then_lowercased_and_stripped() -> None:
    host = Hostname(value="  ExAmple.COM.  ")
    assert host.value == "example.com"


def test_given_invalid_hostname_when_constructed_then_raises() -> None:
    with pytest.raises(DomainError):
        Hostname(value="not a host!")


def test_given_address_when_scheme_missing_then_raises() -> None:
    with pytest.raises(InvalidAddress):
        Address(value="example.com/path")


def test_given_address_when_unsupported_scheme_then_raises() -> None:
    with pytest.raises(InvalidAddress):
        Address(value="ftp://example.com/file")


def test_given_address_when_https_then_parses_host_and_path() -> None:
    addr = Address(value="HTTPS://Example.com/products/1?x=1")
    assert addr.scheme == "https"
    assert addr.host == "example.com"
    assert addr.path == "/products/1"


def test_given_content_hash_when_invalid_hex_then_raises() -> None:
    with pytest.raises(DomainError):
        ContentHash(hex="xyz")


def test_given_content_hash_when_valid_then_str_includes_algo() -> None:
    h = ContentHash(hex="a" * 64)
    assert str(h) == f"sha256:{'a' * 64}"


def test_given_crawl_config_when_timeout_out_of_range_then_raises() -> None:
    with pytest.raises(DomainError):
        CrawlConfig(timeout_seconds=0)
    with pytest.raises(DomainError):
        CrawlConfig(timeout_seconds=301)


def test_given_diff_config_when_regex_invalid_then_raises() -> None:
    with pytest.raises(DomainError):
        DiffConfig(ignore_regexes=["["])


def test_given_politeness_when_negative_concurrency_then_raises() -> None:
    with pytest.raises(InvalidPoliteness):
        Politeness(max_concurrency=0, min_delay_ms=100)


def test_given_interval_when_below_floor_then_raises() -> None:
    with pytest.raises(InvalidInterval):
        Interval(seconds=10, global_minimum=300)


def test_given_interval_when_at_floor_then_ok() -> None:
    i = Interval(seconds=300, global_minimum=300)
    assert i.seconds == 300


def test_given_notification_routing_when_duplicate_channels_then_raises() -> None:
    with pytest.raises(DomainError):
        NotificationRouting(
            channel_ids=["a", "a"],
            triggers={TriggerType.ON_CHANGE},
        )


def test_given_significance_rule_when_invalid_regex_then_raises() -> None:
    with pytest.raises(DomainError):
        SignificanceRule(
            type=SignificanceRuleType.IGNORE_TEXT,
            pattern="[",
            is_regex=True,
        )


def test_given_significance_rule_when_literal_pattern_then_ok() -> None:
    rule = SignificanceRule(
        type=SignificanceRuleType.TRIGGER_TEXT,
        pattern="In stock",
        is_regex=False,
    )
    assert rule.pattern == "In stock"


def test_address_property_host() -> None:
    addr = Address(value="https://example.com/path")
    assert addr.host == "example.com"


def test_address_property_scheme() -> None:
    addr = Address(value="http://example.com/path")
    assert addr.scheme == "http"


def test_address_property_path() -> None:
    addr = Address(value="https://example.com/some/path?q=1")
    assert addr.path == "/some/path"


def test_address_empty_value_raises() -> None:
    with pytest.raises(DomainError):
        Address(value="")


def test_diff_summary_properties() -> None:
    ds = DiffSummary(added_count=5, removed_count=3)
    assert ds.total == 8
    assert ds.is_empty is False

    ds2 = DiffSummary()
    assert ds2.is_empty is True


def test_interval_validation() -> None:
    i = Interval(seconds=500, global_minimum=300)
    assert i.seconds == 500
    assert i.global_minimum == 300


def test_notification_routing_to_dict() -> None:
    nr = NotificationRouting(
        channel_ids=["ch1", "ch2"],
        triggers={TriggerType.ON_CHANGE, TriggerType.ON_ERROR},
    )
    d = nr.to_dict()
    assert d["channel_ids"] == ["ch1", "ch2"]
    assert sorted(d["triggers"]) == ["on_change", "on_error"]


def test_content_hash_invalid_algo_raises() -> None:
    with pytest.raises(DomainError):
        ContentHash(algo="md5", hex="a" * 64)


def test_politeness_negative_delay_raises() -> None:
    with pytest.raises(InvalidPoliteness):
        Politeness(max_concurrency=1, min_delay_ms=-1)
