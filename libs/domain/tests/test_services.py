"""EffectiveConfigResolver: precedence matrix."""

from __future__ import annotations

from datetime import UTC, datetime

from uuid_extensions import uuid7

from lens_domain.entities import Category, Domain, Url
from lens_domain.ids import CategoryId, DomainId, UrlId
from lens_domain.services import EffectiveConfigResolver, GlobalDefaults
from lens_domain.value_objects import (
    CrawlConfig,
    DiffConfig,
    NotificationRouting,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
GLOBALS = GlobalDefaults(
    crawl=CrawlConfig(selector="GLOBAL", timeout_seconds=10),
    diff=DiffConfig(semantic_threshold=0.99, min_text_length=1),
    routing=NotificationRouting(),
)


def _domain() -> Domain:
    return Domain.create(
        id=DomainId(uuid7()),
        host="example.com",
        default_crawl_config=CrawlConfig(selector="DOMAIN"),
        default_diff_config=DiffConfig(semantic_threshold=0.5),
        now=NOW,
    )


def _category(domain: Domain) -> Category:
    return Category.create(
        id=CategoryId(uuid7()),
        domain_id=domain.id_vo,
        name="products",
        crawl_config=CrawlConfig(selector="CATEGORY"),
        diff_config=DiffConfig(semantic_threshold=0.3),
        now=NOW,
    )


def _url(domain: Domain, category: Category | None) -> Url:
    return Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        category_id=category.id_vo if category else None,
        crawl_config=CrawlConfig(selector="URL"),
        diff_config=DiffConfig(semantic_threshold=0.1),
        now=NOW,
    )


def test_given_no_overrides_when_resolve_then_global_wins() -> None:
    domain = Domain.create(
        id=DomainId(uuid7()),
        host="example.com",
        now=NOW,
    )
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    resolver = EffectiveConfigResolver(GLOBALS)
    crawl, diff, routing = resolver.resolve(url, None, domain)
    assert crawl.selector == "GLOBAL"
    assert diff.semantic_threshold == 0.99
    assert routing == GLOBALS.routing


def test_given_domain_override_when_resolve_then_domain_beats_global() -> None:
    domain = _domain()
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        now=NOW,
    )
    resolver = EffectiveConfigResolver(GLOBALS)
    crawl, diff, _ = resolver.resolve(url, None, domain)
    assert crawl.selector == "DOMAIN"
    assert diff.semantic_threshold == 0.5


def test_given_category_override_when_resolve_then_category_beats_domain() -> None:
    domain = _domain()
    category = _category(domain)
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        category_id=category.id_vo,
        now=NOW,
    )
    resolver = EffectiveConfigResolver(GLOBALS)
    crawl, diff, _ = resolver.resolve(url, category, domain)
    assert crawl.selector == "CATEGORY"
    assert diff.semantic_threshold == 0.3


def test_given_url_override_when_resolve_then_url_beats_all() -> None:
    domain = _domain()
    category = _category(domain)
    url = _url(domain, category)
    resolver = EffectiveConfigResolver(GLOBALS)
    crawl, diff, _ = resolver.resolve(url, category, domain)
    assert crawl.selector == "URL"
    assert diff.semantic_threshold == 0.1


def test_given_precedence_chain_when_each_level_sets_field_then_most_specific_wins() -> None:
    domain = Domain.create(
        id=DomainId(uuid7()),
        host="example.com",
        default_crawl_config=CrawlConfig(selector="DOMAIN", timeout_seconds=60),
        now=NOW,
    )
    category = Category.create(
        id=CategoryId(uuid7()),
        domain_id=domain.id_vo,
        name="products",
        now=NOW,
    )
    url = Url.create(
        id=UrlId(uuid7()),
        domain_id=domain.id_vo,
        address="https://example.com/p",
        interval_seconds=600,
        domain_host=domain.host,
        category_id=category.id_vo,
        crawl_config=CrawlConfig(selector="URL", timeout_seconds=5),
        now=NOW,
    )
    resolver = EffectiveConfigResolver(GLOBALS)
    crawl, _, _ = resolver.resolve(url, category, domain)
    assert crawl.selector == "URL"
    assert crawl.timeout_seconds == 5
