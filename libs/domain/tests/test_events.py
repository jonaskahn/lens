"""Domain event shapes: carry required fields and immutable."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from uuid_extensions import uuid7

from lens_domain.events import (
    ChangeEnriched,
    ChangeNeedsEnrichment,
    SiteTemplateDriftDetected,
    UrlBecameStale,
    UrlChangeDetected,
    UrlCrawlFailed,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_given_url_change_detected_when_built_then_carries_ids() -> None:
    eid = uuid7()
    url_id = uuid7()
    change_id = uuid7()
    domain_id = uuid7()
    event = UrlChangeDetected(
        event_id=eid,
        occurred_at=NOW,
        url_id=url_id,
        change_id=change_id,
        domain_id=domain_id,
        category_id=None,
        significant=True,
    )
    assert event.url_id == url_id
    assert event.change_id == change_id
    assert event.significant is True


def test_given_domain_event_when_assigned_to_field_then_frozen() -> None:
    event = UrlBecameStale(
        event_id=uuid7(),
        occurred_at=NOW,
        url_id=uuid7(),
        domain_id=uuid7(),
        category_id=None,
    )
    with pytest.raises(FrozenInstanceError):
        event.url_id = uuid7()  # type: ignore[misc]


def test_given_url_crawl_failed_when_built_then_stores_error() -> None:
    event = UrlCrawlFailed(
        event_id=uuid7(),
        occurred_at=NOW,
        url_id=uuid7(),
        domain_id=uuid7(),
        category_id=None,
        error="timeout",
        consecutive_errors=3,
    )
    assert event.error == "timeout"
    assert event.consecutive_errors == 3


def test_given_change_needs_enrichment_when_built_then_carries_zones() -> None:
    event = ChangeNeedsEnrichment(
        event_id=uuid7(),
        occurred_at=NOW,
        url_id=uuid7(),
        change_id=uuid7(),
        domain_id=uuid7(),
        category_id=None,
        template_class="ecommerce",
        escalation_reasons=("signal_disagreement",),
        changed_zones=({"zone_name": "price", "previous_text": "$9", "current_text": "$7"},),
    )
    assert event.template_class == "ecommerce"
    assert event.changed_zones[0]["zone_name"] == "price"


def test_given_change_enriched_when_built_then_carries_classification() -> None:
    event = ChangeEnriched(
        event_id=uuid7(),
        occurred_at=NOW,
        url_id=uuid7(),
        change_id=uuid7(),
        domain_id=uuid7(),
        category_id=None,
        classification={
            "change_type": "price",
            "is_meaningful": True,
            "severity": 4,
            "summary": "Price dropped",
            "extracted_fields": {},
            "confidence": 0.9,
            "model_id": "qwen",
        },
    )
    assert event.classification["change_type"] == "price"


def test_given_template_drift_when_built_then_carries_versions() -> None:
    event = SiteTemplateDriftDetected(
        event_id=uuid7(),
        occurred_at=NOW,
        domain="shop.example.com",
        url_pattern="/p/[^/]+",
        profile_id=uuid7(),
        old_template_hash="a" * 32,
        new_template_hash="b" * 32,
        old_version=4,
        new_version=5,
        sample_url="https://shop.example.com/p/1",
    )
    assert event.old_version == 4
    assert event.new_version == 5
