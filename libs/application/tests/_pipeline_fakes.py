"""In-memory port fakes for the crawl pipeline use cases."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from lens_application.pipeline import (
    BlobStoragePort,
    CrawlTask,
    DifferPort,
    DiffResult,
    HtmlNormalizerPort,
    LockPort,
    NormalizedContent,
    RawFetchResult,
    TaskPublisherPort,
)
from lens_domain.value_objects import (
    ContentHash,
    DiffConfig,
)


class InMemoryBlobStorage(BlobStoragePort):
    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes) -> str:
        self._store[key] = data
        return key

    async def get(self, key: str) -> bytes:
        if key not in self._store:
            raise KeyError(key)
        return self._store[key]

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class InMemoryCrawler:
    """Configurable :class:`CrawlerPort` fake for tests."""

    def __init__(self, *, html: str = "<html>ok</html>", status: int = 200) -> None:
        self.html = html
        self.status = status
        self.calls: list[str] = []

    async def fetch(self, url: str, config: Any) -> RawFetchResult:
        self.calls.append(url)
        from datetime import UTC, datetime

        return RawFetchResult(
            html=self.html,
            http_status=self.status,
            byte_size=len(self.html.encode("utf-8")),
            fetched_at=datetime.now(UTC),
        )


class InMemoryNormalizer(HtmlNormalizerPort):
    def __init__(self, text: str | None = None) -> None:
        self._text = text

    async def normalize(self, html: str, config: DiffConfig) -> NormalizedContent:
        from hashlib import sha256

        text = html if self._text is None else self._text
        return NormalizedContent(
            text=text,
            hash=ContentHash(hex=sha256(text.encode("utf-8")).hexdigest()),
        )


class InMemoryDiffer(DifferPort):
    def __init__(self) -> None:
        self.calls: list[UUID] = []

    async def diff(
        self,
        previous: str,
        current: str,
        config: DiffConfig,
        change_id: UUID,
        blob_storage: BlobStoragePort,
    ) -> DiffResult:
        from lens_domain.value_objects import DiffSummary

        self.calls.append(change_id)
        added = max(0, len(current) - len(previous))
        removed = max(0, len(previous) - len(current))
        ref = f"diffs/{change_id}.diff.gz"
        await blob_storage.put(ref, current.encode("utf-8"))
        return DiffResult(
            summary=DiffSummary(added_count=added, removed_count=removed),
            diff_ref=ref,
            unified_diff=current,
        )


class InMemoryTaskPublisher(TaskPublisherPort):
    def __init__(self) -> None:
        self.published: list[CrawlTask] = []

    async def publish_crawl_task(self, task: CrawlTask) -> None:
        self.published.append(task)


class InMemoryLock(LockPort):
    def __init__(self) -> None:
        self._held: dict[str, str] = {}

    async def acquire(self, key: str, *, ttl_seconds: int, token: str) -> str:
        if key in self._held:
            return ""
        self._held[key] = token
        return token

    async def release(self, key: str, token: str) -> None:
        if self._held.get(key) == token:
            del self._held[key]

    async def renew(self, key: str, token: str, *, ttl_seconds: int) -> bool:
        return self._held.get(key) == token


__all__ = [
    "InMemoryBlobStorage",
    "InMemoryCrawler",
    "InMemoryDiffer",
    "InMemoryLock",
    "InMemoryNormalizer",
    "InMemoryTaskPublisher",
]
