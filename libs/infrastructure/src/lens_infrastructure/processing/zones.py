"""Zone extractor adapter: applies ZoneSelector CSS selectors to HTML using lxml+html5lib.

Extracts the inner text of matching DOM elements for each named zone,
collapses whitespace, and returns ``{zone_name: text}``.
"""

from __future__ import annotations

from lxml import etree  # type: ignore[import-untyped]
from lxml.cssselect import CSSSelector  # type: ignore[import-untyped]

from lens_domain.value_objects import ZoneSelector

__all__ = ["ZoneExtractor"]


class ZoneExtractor:
    """Apply :class:`ZoneSelector` selectors to HTML and return zone texts."""

    def extract(
        self,
        html: str,
        selectors: list[ZoneSelector],
    ) -> dict[str, str]:
        try:
            document = etree.fromstring(html, parser=etree.HTMLParser())
        except etree.XMLSyntaxError:
            document = etree.fromstring(html, parser=etree.HTMLParser(recover=True))

        result: dict[str, str] = {}
        for selector in selectors:
            matched = CSSSelector(selector.css_selector)(document)
            parts: list[str] = []
            for element in matched:
                text = _extract_inner_text(element)
                if text:
                    parts.append(text)
            result[selector.name] = " ".join(parts)
        return result


def _extract_inner_text(element: etree._Element) -> str:
    return _collapse_whitespace(etree.tostring(element, method="text", encoding="unicode"))


def _collapse_whitespace(text: str) -> str:
    return " ".join(text.split())
