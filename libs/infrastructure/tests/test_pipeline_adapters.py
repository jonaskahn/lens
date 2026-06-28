"""Tests for the HTML normaliser and differ adapters."""

from __future__ import annotations

from uuid import uuid4

import pytest

from lens_domain.value_objects import DiffConfig
from lens_infrastructure.differ import LineBasedDiffer
from lens_infrastructure.normalizer import RegexHtmlNormalizer
from lens_infrastructure.storage import (
    AsyncLocalFileBlobStorage,
    LocalFileBlobStorage,
)


@pytest.mark.asyncio
async def test_given_html_with_script_and_style_when_normalize_then_stripped() -> None:
    normalizer = RegexHtmlNormalizer()
    html = (
        "<html><head><style>body { color: red; }</style></head>"
        "<body><p>Hello <script>evil()</script>world</p></body></html>"
    )
    content = await normalizer.normalize(html, DiffConfig())
    assert "<script>" not in content.text
    assert "<style>" not in content.text
    assert "Hello world" in content.text


@pytest.mark.asyncio
async def test_given_repeated_whitespace_when_normalize_then_collapsed() -> None:
    normalizer = RegexHtmlNormalizer()
    content = await normalizer.normalize(
        "<p>line   one\n\n\nline\t\t two</p>",
        DiffConfig(),
    )
    assert "  " not in content.text
    assert content.text == "line one line two"


@pytest.mark.asyncio
async def test_given_normalized_text_when_diff_then_unified_diff_returned(
    tmp_path,
) -> None:
    differ = LineBasedDiffer()
    storage = AsyncLocalFileBlobStorage(
        inner=LocalFileBlobStorage(root=tmp_path),
    )
    result = await differ.diff(
        previous="line one\nline two",
        current="line one\nline two changed",
        config=DiffConfig(),
        change_id=uuid4(),
        blob_storage=storage,
    )
    assert result.summary.added_count >= 1
    assert result.diff_ref.startswith("diffs/")
    assert "+" in result.unified_diff or "-" in result.unified_diff
    raw = await storage.get(result.diff_ref)
    assert raw.decode("utf-8") == result.unified_diff
