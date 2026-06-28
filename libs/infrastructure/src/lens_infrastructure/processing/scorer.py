"""Semantic scorer adapter: Jaccard token distance with typed-entity bonuses.

Implements the two-component scoring algorithm from 07 §8.3.
"""

from __future__ import annotations

import re
from collections.abc import Callable

__all__ = ["SemanticScorer"]

_STOPWORDS: set[str] = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    "will",
    "would",
    "shall",
    "should",
    "can",
    "could",
    "may",
    "might",
    "must",
    "ought",
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
    "my",
    "your",
    "his",
    "its",
    "our",
    "their",
    "mine",
    "yours",
    "hers",
    "ours",
    "theirs",
    "this",
    "that",
    "these",
    "those",
    "am",
    "at",
    "by",
    "for",
    "with",
    "about",
    "between",
    "into",
    "through",
    "during",
    "before",
    "after",
    "above",
    "below",
    "from",
    "up",
    "down",
    "in",
    "out",
    "on",
    "off",
    "over",
    "under",
    "again",
    "further",
    "then",
    "once",
    "here",
    "there",
    "when",
    "where",
    "why",
    "how",
    "all",
    "each",
    "every",
    "both",
    "few",
    "more",
    "most",
    "other",
    "some",
    "such",
    "no",
    "nor",
    "not",
    "only",
    "same",
    "so",
    "than",
    "too",
    "very",
    "just",
    "and",
    "but",
    "or",
    "if",
    "while",
    "as",
    "until",
    "of",
    "to",
    "also",
    "der",
    "die",
    "das",
    "und",
    "ist",
    "sind",
    "war",
    "den",
    "mit",
    "auf",
    "für",
    "von",
    "ein",
    "eine",
    "einen",
    "nicht",
    "sich",
    "des",
    "dem",
    "als",
    "auch",
    "es",
    "werden",
    "aus",
    "er",
    "sie",
}

_PRICE_RE = re.compile(r"(?:[$€£¥]\s*)?(?:[\d,]+)(?:\.\d{1,2})?\s*(?:[$€£¥])?")
_DATE_ISO_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_DATE_DMY_RE = re.compile(r"\b\d{2}[./]\d{2}[./]\d{4}\b")
_DATE_US_RE = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w* \d{1,2},? \d{4}\b")
_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_URL_RE = re.compile(r"https?://[^\s]+")


def _extract_prices(text: str) -> set[str]:
    return {m.group(0) for m in _PRICE_RE.finditer(text)}


def _extract_dates(text: str) -> set[str]:
    return {
        m.group(0)
        for m in re.finditer(
            rf"{_DATE_ISO_RE.pattern}|{_DATE_DMY_RE.pattern}|{_DATE_US_RE.pattern}",
            text,
        )
    }


def _extract_numbers(text: str) -> set[str]:
    return {m.group(0) for m in _NUMBER_RE.finditer(text)}


def _extract_urls(text: str) -> set[str]:
    return {m.group(0) for m in _URL_RE.finditer(text)}


_ENTITY_EXTRACTORS: list[tuple[str, Callable[[str], set[str]], float]] = [
    ("price", _extract_prices, 0.40),
    ("date", _extract_dates, 0.20),
    ("number", _extract_numbers, 0.10),
    ("url", _extract_urls, 0.05),
]


def _tokenize(text: str) -> set[str]:
    tokens = set()
    for token in re.split(r"\W+", text.lower()):
        if len(token) < 2:
            continue
        if token in _STOPWORDS:
            continue
        tokens.add(token)
    return tokens


class SemanticScorer:
    """Jaccard-distance scorer with typed-entity delta bonuses."""

    def score(self, old_text: str, new_text: str) -> float:
        old_tokens = _tokenize(old_text)
        new_tokens = _tokenize(new_text)
        if not old_tokens and not new_tokens:
            return 0.0
        intersection = old_tokens & new_tokens
        union = old_tokens | new_tokens
        jaccard = 1.0 - (len(intersection) / len(union))
        entity_bonus = self._entity_delta(old_text, new_text)
        return min(1.0, jaccard + entity_bonus)

    def score_zone_weighted(
        self,
        old_text: str,
        new_text: str,
        zone_weight: float,
    ) -> float:
        base = self.score(old_text, new_text)
        return base * zone_weight

    @staticmethod
    def _entity_delta(old_text: str, new_text: str) -> float:
        bonus = 0.0
        for _name, extractor, weight in _ENTITY_EXTRACTORS:
            old_entities = extractor(old_text)
            new_entities = extractor(new_text)
            if old_entities != new_entities:
                bonus += weight
        return bonus
