"""Template fingerprint adapter: DOM skeleton extraction and hashing.

Produces a canonical, structure-only representation of HTML suitable for
detecting template-level changes (L2), insensitive to text, attribute
values, script/style content, and CSS build-tool suffixes.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser

__all__ = ["TemplateFingerprint"]

_HEX_SUFFIX_RE = re.compile(r"[a-f0-9]{6,8}$")
_NUMERIC_SUFFIX_RE = re.compile(r"-\d+$")
_STRUCTURAL_ATTRS = frozenset(
    {
        "role",
        "aria-label",
        "aria-labelledby",
        "aria-describedby",
        "aria-hidden",
        "aria-expanded",
        "type",
        "name",
        "itemprop",
        "itemtype",
        "itemscope",
        "hidden",
        "disabled",
        "required",
        "checked",
        "selected",
        "readonly",
        "placeholder",
        "title",
        "lang",
        "dir",
    }
)
_STRIP_ATTR_PREFIXES = ("on", "data-")
_CLASS_IGNORE_PREFIX = ("aria-", "fa-", "glyphicon-", "icon-")


class _SkeletonBuilder(HTMLParser):
    """Streaming HTML parser that builds a canonical DOM skeleton string."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._lines: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._lines.append(self._render_tag(tag.lower(), attrs))
        if tag.lower() not in _VOID_ELEMENTS:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() not in _VOID_ELEMENTS:
            self._depth -= 1

    def handle_data(self, data: str) -> None:
        return

    def handle_entityref(self, name: str) -> None:
        return

    def handle_charref(self, name: str) -> None:
        return

    def _render_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> str:
        kept: list[str] = []
        for name, value in attrs:
            name_lower = name.lower()
            if name_lower.startswith(_STRIP_ATTR_PREFIXES):
                continue
            if name_lower == "class" and value is not None:
                normalized = _normalize_class(value)
                if normalized:
                    kept.append(f'class="{normalized}"')
            elif name_lower == "id":
                kept.append('id=""')
            elif name_lower in _STRUCTURAL_ATTRS:
                kept.append(f'{name_lower}="{value or ""}"')
            elif name_lower in ("href", "src", "action"):
                kept.append(f'{name_lower}=""')
        attrs_str = " ".join(sorted(kept))
        if attrs_str:
            return f"{'  ' * self._depth}<{tag} {attrs_str}>"
        return f"{'  ' * self._depth}<{tag}>"

    def build(self) -> str:
        return "\n".join(self._lines)


_VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


def _normalize_class(class_str: str) -> str:
    tokens = class_str.split()
    filtered: list[str] = []
    for token in tokens:
        lowered = token.lower()
        if any(lowered.startswith(p) for p in _CLASS_IGNORE_PREFIX):
            continue
        if _HEX_SUFFIX_RE.match(token):
            continue
        if _NUMERIC_SUFFIX_RE.search(token):
            continue
        filtered.append(token)
    filtered.sort()
    return " ".join(filtered)


class TemplateFingerprint:
    """Extract a canonical DOM skeleton and compute its hash."""

    def extract_skeleton(self, html: str) -> str:
        builder = _SkeletonBuilder()
        builder.feed(html)
        return builder.build()

    def hash_skeleton(self, skeleton: str) -> str:
        return hashlib.md5(skeleton.encode("utf-8")).hexdigest()
