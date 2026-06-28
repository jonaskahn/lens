"""HTML normalisation adapter.

The normaliser strips script/style blocks, collapses whitespace, and
returns a stable plain-text representation. CSS-selector scoping and
``ignore_selectors`` are tracked but not yet applied; a future
``ZoneExtractorPort`` will provide the proper zone-based extraction.
For now the full document text is normalised.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from lens_application.pipeline import HtmlNormalizerPort, NormalizedContent
from lens_domain.value_objects import ContentHash, DiffConfig

__all__ = ["RegexHtmlNormalizer"]


_WHITESPACE_RE = re.compile(r"\s+")
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_NOSCRIPT_RE = re.compile(r"<noscript\b[^>]*>.*?</noscript>", re.IGNORECASE | re.DOTALL)


class _TextExtractor(HTMLParser):
    """HTMLParser that concatenates text nodes and skips script/style."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0
        self._skip_tags = {"script", "style", "noscript"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._skip_tags:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._skip_tags and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data:
            self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


class RegexHtmlNormalizer(HtmlNormalizerPort):
    """A stdlib-only HTML normaliser that strips tags and collapses whitespace.

    Selector scoping (CrawlConfig.selector) and ignore_selectors are
    accepted for forward compatibility but currently ignored - the
    entire document is normalised. A future revision introduces the
    proper zone-based extraction.
    """

    async def normalize(self, html: str, config: DiffConfig) -> NormalizedContent:
        text = self._strip_text(html)
        text = self._apply_ignore_regexes(text, config)
        text = _WHITESPACE_RE.sub(" ", text).strip()
        digest = _sha256_hex(text.encode("utf-8"))
        return NormalizedContent(
            text=text,
            hash=ContentHash(hex=digest),
        )

    @staticmethod
    def _strip_text(html: str) -> str:
        # Cheap pre-pass to keep the parser small on huge pages.
        cleaned = _SCRIPT_RE.sub(" ", html)
        cleaned = _STYLE_RE.sub(" ", cleaned)
        cleaned = _NOSCRIPT_RE.sub(" ", cleaned)
        cleaned = _TAG_RE.sub(" ", cleaned)
        # Now feed the residue to the parser for any entity-decoding issues.
        parser = _TextExtractor()
        try:
            parser.feed(cleaned)
            parser.close()
        except Exception:
            return cleaned
        return parser.text() or cleaned

    @staticmethod
    def _apply_ignore_regexes(text: str, config: DiffConfig) -> str:
        if not config.ignore_regexes:
            return text
        kept: list[str] = []
        for line in text.splitlines():
            if any(re.search(p, line) for p in config.ignore_regexes):
                continue
            kept.append(line)
        return "\n".join(kept)


def _sha256_hex(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
