"""Tests for L2-L4 pipeline adapters: fingerprint, zone extractor, scorer, classifier."""

from __future__ import annotations

from lens_domain.value_objects import ZoneSelector
from lens_infrastructure.processing import (
    SemanticScorer,
    TemplateClassifier,
    TemplateFingerprint,
    ZoneExtractor,
)


class TestTemplateFingerprint:
    def test_given_simple_html_when_extracting_skeleton_then_strips_text_and_values(self):
        fingerprint = TemplateFingerprint()
        html = """<html><body><div class="product-card ab12ef" data-id="42">
            <h2 class="title-1a2b3c">Blue Widget</h2>
            <span class="price">$9.99</span>
        </div></body></html>"""
        skeleton = fingerprint.extract_skeleton(html)
        assert "Blue Widget" not in skeleton
        assert "$9.99" not in skeleton
        assert "ab12ef" not in skeleton
        assert "product-card" in skeleton
        assert "class=" in skeleton

    def test_given_identical_skeleton_when_hashing_then_same_hash(self):
        fingerprint = TemplateFingerprint()
        html1 = """<div class="product ab12ef"><h2>Product A</h2></div>"""
        html2 = """<div class="product cd34ef"><h2>Product B</h2></div>"""
        skel1 = fingerprint.extract_skeleton(html1)
        skel2 = fingerprint.extract_skeleton(html2)
        assert fingerprint.hash_skeleton(skel1) == fingerprint.hash_skeleton(skel2)

    def test_given_different_structure_when_hashing_then_different_hash(self):
        fingerprint = TemplateFingerprint()
        html1 = """<div><h2>Title</h2></div>"""
        html2 = """<div><h2>Title</h2><span>Extra</span></div>"""
        assert fingerprint.hash_skeleton(
            fingerprint.extract_skeleton(html1),
        ) != fingerprint.hash_skeleton(
            fingerprint.extract_skeleton(html2),
        )


class TestZoneExtractor:
    def test_given_matching_selector_when_extracting_then_returns_text(self):
        extractor = ZoneExtractor()
        html = """<html><body><div class="price">$9.99</div></body></html>"""
        selectors = [ZoneSelector(name="price", css_selector=".price", weight=1.0)]
        result = extractor.extract(html, selectors)
        assert result["price"] == "$9.99"

    def test_given_non_matching_selector_when_extracting_then_returns_empty_string(self):
        extractor = ZoneExtractor()
        html = """<html><body><div class="title">Hello</div></body></html>"""
        selectors = [ZoneSelector(name="price", css_selector=".price", weight=1.0)]
        result = extractor.extract(html, selectors)
        assert result["price"] == ""

    def test_given_malformed_html_when_extracting_then_recovers_gracefully(self):
        extractor = ZoneExtractor()
        html = """<div><p>Broken <b>markup</i> here</span>"""
        selectors = [ZoneSelector(name="main", css_selector="div", weight=1.0)]
        result = extractor.extract(html, selectors)
        assert "Broken" in result["main"]


class TestSemanticScorer:
    def test_given_identical_texts_when_scoring_then_score_is_zero(self):
        scorer = SemanticScorer()
        assert scorer.score("hello world", "hello world") == 0.0

    def test_given_completely_different_texts_when_scoring_then_score_high(self):
        scorer = SemanticScorer()
        score = scorer.score("hello world", "foo bar baz")
        assert score > 0.5

    def test_given_price_value_changed_when_scoring_then_score_includes_entity_bonus(self):
        scorer = SemanticScorer()
        score_no_price = scorer.score("available", "shipped")
        score_with_price = scorer.score("price: $9.99", "price: $12.99")
        assert score_with_price >= score_no_price or score_with_price > 0.3

    def test_given_whitespace_only_change_when_scoring_then_score_below_threshold(self):
        scorer = SemanticScorer()
        score = scorer.score("hello  world", "hello world")
        assert score < 0.3


class TestTemplateClassifier:
    def test_given_woocommerce_page_when_classifying_then_returns_ecommerce_woocommerce(self):
        classifier = TemplateClassifier()
        html = '<html><body class="woocommerce">Shop</body></html>'
        result = classifier.classify(html)
        assert result == "ecommerce/woocommerce"

    def test_given_wordpress_page_when_classifying_then_returns_cms_wordpress(self):
        classifier = TemplateClassifier()
        html = '<html><body><img src="/wp-content/uploads/img.png"></body></html>'
        result = classifier.classify(html)
        assert result == "cms/wordpress"

    def test_given_unknown_page_when_classifying_then_returns_none(self):
        classifier = TemplateClassifier()
        html = "<html><body>Hello</body></html>"
        result = classifier.classify(html)
        assert result is None

    def test_given_class_name_when_zones_for_class_then_returns_specific_selectors(self):
        classifier = TemplateClassifier()
        zones = classifier.zones_for_class("generic/product")
        assert len(zones) > 0
        prices = [z for z in zones if z.name == "price"]
        assert len(prices) == 1
        assert prices[0].weight == 2.0
