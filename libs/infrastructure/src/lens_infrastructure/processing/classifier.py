"""Template classifier adapter: regex-based platform detection from raw HTML.

Matches against known CMS/ecommerce signals as defined in 07 §8.4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lens_domain.value_objects import ZoneSelector

__all__ = ["TemplateClassifier"]


@dataclass(frozen=True, slots=True)
class _ClassEntry:
    name: str
    patterns: list[str]
    zones: list[ZoneSelector]


_CLASSIFIER_RULES: list[_ClassEntry] = [
    _ClassEntry(
        name="ecommerce/woocommerce",
        patterns=[r"class=[\"'][^\"']*woocommerce"],
        zones=[
            ZoneSelector(
                name="price",
                css_selector=".price .amount, .woocommerce-Price-amount, [itemprop='price']",
                weight=2.0,
            ),
            ZoneSelector(
                name="stock",
                css_selector=".stock, .in-stock, .out-of-stock, [itemprop='availability']",
                weight=1.5,
            ),
            ZoneSelector(
                name="product_title",
                css_selector=".product_title, .entry-title, h1[itemprop='name']",
                weight=1.0,
            ),
            ZoneSelector(
                name="description",
                css_selector=".woocommerce-product-details__short-description, [itemprop='description']",
                weight=0.5,
            ),
            ZoneSelector(
                name="navigation",
                css_selector="nav, .woocommerce-breadcrumb, .nav",
                weight=0.0,
                is_noise=True,
            ),
            ZoneSelector(
                name="footer",
                css_selector="footer, .site-footer, .footer",
                weight=0.0,
                is_noise=True,
            ),
        ],
    ),
    _ClassEntry(
        name="ecommerce/shopify",
        patterns=[r"Shopify\.shop\s*="],
        zones=[
            ZoneSelector(name="product_title", css_selector=".product__title, h1", weight=1.0),
            ZoneSelector(name="price", css_selector=".price__regular, .price-item, [data-price]", weight=2.0),
            ZoneSelector(
                name="variant_selector",
                css_selector=".product-form__input, variant-selects",
                weight=1.5,
            ),
            ZoneSelector(
                name="navigation",
                css_selector="nav, .header__menu, .nav",
                weight=0.0,
                is_noise=True,
            ),
            ZoneSelector(name="footer", css_selector="footer, .footer", weight=0.0, is_noise=True),
        ],
    ),
    _ClassEntry(
        name="ecommerce/magento",
        patterns=[r"(?:Mage\.Cookies|require\([\"']Magento_)"],
        zones=[
            ZoneSelector(name="product_name", css_selector=".product-name, h1.page-title", weight=1.0),
            ZoneSelector(
                name="price_box",
                css_selector=".price-box, .product-price, [data-price-type='finalPrice']",
                weight=2.0,
            ),
            ZoneSelector(name="availability", css_selector=".availability, .stock", weight=1.5),
            ZoneSelector(name="navigation", css_selector="nav, .breadcrumbs, .nav", weight=0.0, is_noise=True),
            ZoneSelector(
                name="footer",
                css_selector="footer, .page-footer, .footer",
                weight=0.0,
                is_noise=True,
            ),
        ],
    ),
    _ClassEntry(
        name="cms/wordpress",
        patterns=[r"(?:/wp-content/|/wp-includes/)"],
        zones=[
            ZoneSelector(name="entry_title", css_selector=".entry-title, .post-title, h1", weight=1.0),
            ZoneSelector(
                name="entry_content",
                css_selector=".entry-content, .post-content, article .content",
                weight=1.0,
            ),
            ZoneSelector(
                name="entry_date",
                css_selector=".entry-date, .post-date, time.entry-date",
                weight=0.5,
            ),
            ZoneSelector(
                name="navigation",
                css_selector="nav, .nav, .menu, .wp-block-navigation",
                weight=0.0,
                is_noise=True,
            ),
            ZoneSelector(
                name="footer",
                css_selector="footer, .site-footer, .footer",
                weight=0.0,
                is_noise=True,
            ),
        ],
    ),
    _ClassEntry(
        name="cms/drupal",
        patterns=[r"Drupal\.settings"],
        zones=[
            ZoneSelector(name="node_title", css_selector=".node__title, h1, .page-title", weight=1.0),
            ZoneSelector(
                name="field_body",
                css_selector=".field--body, .node__content, article .content",
                weight=1.0,
            ),
            ZoneSelector(
                name="navigation",
                css_selector="nav, .nav, .menu, .breadcrumb",
                weight=0.0,
                is_noise=True,
            ),
            ZoneSelector(
                name="footer",
                css_selector="footer, .site-footer, .footer",
                weight=0.0,
                is_noise=True,
            ),
        ],
    ),
    _ClassEntry(
        name="generic/article",
        patterns=[r"<article[\s>]"],
        zones=[
            ZoneSelector(name="article_title", css_selector="h1, [itemprop='headline']", weight=1.0),
            ZoneSelector(
                name="article_body",
                css_selector="article, [itemprop='articleBody'], .post-body",
                weight=1.0,
            ),
            ZoneSelector(
                name="publish_date",
                css_selector="time, [itemprop='datePublished'], .date",
                weight=0.5,
            ),
            ZoneSelector(name="navigation", css_selector="nav, .nav", weight=0.0, is_noise=True),
            ZoneSelector(name="footer", css_selector="footer, .footer", weight=0.0, is_noise=True),
        ],
    ),
    _ClassEntry(
        name="generic/product",
        patterns=[r"itemtype=[\"']https?://schema\.org/Product"],
        zones=[
            ZoneSelector(name="name", css_selector="[itemprop='name'], h1", weight=1.0),
            ZoneSelector(name="price", css_selector="[itemprop='price'], .price", weight=2.0),
            ZoneSelector(name="description", css_selector="[itemprop='description']", weight=0.5),
            ZoneSelector(name="navigation", css_selector="nav, .nav", weight=0.0, is_noise=True),
            ZoneSelector(name="footer", css_selector="footer, .footer", weight=0.0, is_noise=True),
        ],
    ),
]

_GENERIC_FALLBACK: list[ZoneSelector] = [
    ZoneSelector(
        name="main_content",
        css_selector="main, [role='main'], article, .main-content, #main, #content, .content",
        weight=1.0,
    ),
    ZoneSelector(
        name="navigation",
        css_selector="nav, header nav, [role='navigation'], .nav, #nav",
        weight=0.0,
        is_noise=True,
    ),
    ZoneSelector(name="sidebar", css_selector="aside, [role='complementary'], .sidebar, #sidebar", weight=0.3),
    ZoneSelector(
        name="footer",
        css_selector="footer, [role='contentinfo'], .footer, #footer",
        weight=0.0,
        is_noise=True,
    ),
]


class TemplateClassifier:
    """Classify a page's platform/template from raw HTML via regex patterns."""

    def classify(self, html: str) -> str | None:
        for entry in _CLASSIFIER_RULES:
            if all(re.search(p, html, re.IGNORECASE) for p in entry.patterns):
                return entry.name
        return None

    def zones_for_class(self, class_name: str) -> list[ZoneSelector]:
        for entry in _CLASSIFIER_RULES:
            if entry.name == class_name:
                return list(entry.zones)
        return list(_GENERIC_FALLBACK)
