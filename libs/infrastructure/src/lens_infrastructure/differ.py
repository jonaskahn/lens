"""Line-based unified differ adapter.

Uses Python's stdlib :mod:`difflib` to compute a unified diff between
previous and current normalised text, stores the gzip-compressed diff in
the supplied :class:`BlobStoragePort`, and returns a :class:`DiffResult`
with the summary counts and the blob reference.
"""

from __future__ import annotations

import difflib
from typing import Any
from uuid import UUID

from lens_application.pipeline import BlobStoragePort, DifferPort, DiffResult
from lens_domain.value_objects import DiffConfig, DiffSummary

__all__ = ["LineBasedDiffer"]


class LineBasedDiffer(DifferPort):
    """Produce a unified diff between two normalised text blobs."""

    def __init__(self, *, context_lines: int = 3) -> None:
        self._context = context_lines

    async def diff(
        self,
        previous: str,
        current: str,
        config: DiffConfig,
        change_id: UUID,
        blob_storage: BlobStoragePort,
    ) -> DiffResult:
        previous_lines = self._split(previous, config)
        current_lines = self._split(current, config)
        diff_lines = list(
            difflib.unified_diff(
                previous_lines,
                current_lines,
                fromfile="previous",
                tofile="current",
                n=self._context,
            ),
        )
        unified = "\n".join(diff_lines)
        added, removed = self._count_differences(diff_lines)
        diff_ref = f"diffs/{change_id}.diff.gz"
        await blob_storage.put(diff_ref, unified.encode("utf-8"))
        return DiffResult(
            summary=DiffSummary(added_count=added, removed_count=removed),
            diff_ref=diff_ref,
            unified_diff=unified,
        )

    @staticmethod
    def _split(text: str, config: DiffConfig) -> list[str]:
        lines = text.splitlines()
        if not config.ignore_regexes:
            return lines
        import re

        kept: list[str] = []
        for line in lines:
            if any(re.search(p, line) for p in config.ignore_regexes):
                continue
            kept.append(line)
        return kept

    @staticmethod
    def _count_differences(diff_lines: Any) -> tuple[int, int]:
        added = 0
        removed = 0
        for line in diff_lines:
            if not line:
                continue
            tag = line[0]
            if tag == "+":
                added += 1
            elif tag == "-":
                removed += 1
        return added, removed
