from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

__all__ = [
    "RetentionAdapter",
]


class RetentionAdapter:
    def __init__(
        self,
        *,
        max_snapshots: int = 25,
        blob_delete_fn: Callable[[str], Any],
    ) -> None:
        self._max_snapshots = max_snapshots
        self._blob_delete = blob_delete_fn

    async def enforce(self, url_id: str, snapshots: list[dict[str, Any]]) -> int:
        excess = len(snapshots) - self._max_snapshots
        if excess <= 0:
            return 0
        evicted = 0
        for snapshot in sorted(
            snapshots,
            key=lambda s: s.get("fetched_at", ""),
        )[:excess]:
            ref = snapshot.get("content_ref")
            if ref:
                await self._blob_delete(ref)
            evicted += 1
        return evicted

    async def sweep_orphan_blobs(
        self,
        blob_keys: Iterable[str],
        active_refs: set[str],
    ) -> int:
        count = 0
        for key in blob_keys:
            if key not in active_refs:
                await self._blob_delete(key)
                count += 1
        return count
