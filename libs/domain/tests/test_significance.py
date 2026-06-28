"""Tests for :class:`lens_domain.services.ChangeSignificanceEvaluator`."""

from __future__ import annotations

from lens_domain.enums import SignificanceRuleType
from lens_domain.services import ChangeSignificanceEvaluator
from lens_domain.value_objects import (
    DiffConfig,
    SignificanceRule,
)

EVAL = ChangeSignificanceEvaluator()


def _config(*, rules=None, min_text_length: int = 5) -> DiffConfig:
    return DiffConfig(
        significance_rules=list(rules or []),
        min_text_length=min_text_length,
    )


def test_given_ignore_rule_matches_when_evaluate_then_insignificant() -> None:
    rule = SignificanceRule(
        type=SignificanceRuleType.IGNORE_TEXT,
        pattern="price changed",
    )
    config = _config(rules=[rule], min_text_length=20)
    assert EVAL.evaluate("price changed\nnew line", config) is False


def test_given_ignore_rule_no_match_when_evaluate_then_significant() -> None:
    rule = SignificanceRule(
        type=SignificanceRuleType.IGNORE_TEXT,
        pattern="price changed",
    )
    config = _config(rules=[rule])
    assert EVAL.evaluate("totally different content here please", config) is True


def test_given_trigger_rule_not_matched_when_evaluate_then_insignificant() -> None:
    rule = SignificanceRule(
        type=SignificanceRuleType.TRIGGER_TEXT,
        pattern="In stock",
    )
    config = _config(rules=[rule])
    assert EVAL.evaluate("out of stock now", config) is False


def test_given_exclusion_present_when_evaluate_then_insignificant() -> None:
    rule = SignificanceRule(
        type=SignificanceRuleType.TEXT_MUST_NOT_BE_PRESENT,
        pattern="Advertisement",
    )
    config = _config(rules=[rule])
    assert EVAL.evaluate("Advertisement: new banner", config) is False


def test_given_text_below_min_length_when_evaluate_then_insignificant() -> None:
    config = _config(min_text_length=20)
    assert EVAL.evaluate("short change", config) is False


def test_given_regex_ignore_rule_when_matches_then_insignificant() -> None:
    rule = SignificanceRule(
        type=SignificanceRuleType.IGNORE_TEXT,
        pattern=r"\d{4}-\d{2}-\d{2}",
        is_regex=True,
    )
    config = _config(rules=[rule])
    assert EVAL.evaluate("Today is 2026-01-27 only", config) is False
