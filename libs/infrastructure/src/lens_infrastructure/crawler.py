"""Default :class:`CrawlerPort` adapter (httpx-based).

A thin :class:`HttpxCrawler` is shipped backed by ``httpx`` so the
worker can fetch real pages. The crawl4ai implementation can be
swapped in to honour ``CrawlConfig.js_enabled``, ``wait_for``, and the
browser pool. For now :class:`HttpxCrawler` honours
``timeout_seconds`` and returns the response body, status, headers, and
fetched-at timestamp as a :class:`RawFetchResult`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from lens_application.pipeline import CrawlerPort, RawFetchResult
from lens_domain.value_objects import CrawlConfig

__all__ = ["HttpxCrawler"]


class HttpxCrawler(CrawlerPort):
    """An httpx-backed :class:`CrawlerPort` for non-JS URLs."""

    def __init__(self, *, client: Any | None = None, follow_redirects: bool = True) -> None:
        self._client = client
        self._owns_client = client is None
        self._follow_redirects = follow_redirects

    async def fetch(self, url: str, config: CrawlConfig) -> RawFetchResult:
        client = await self._ensure_client()
        try:
            response = await client.get(
                url,
                headers=config.headers,
                timeout=config.timeout_seconds,
                follow_redirects=self._follow_redirects,
            )
        except Exception as exc:
            return RawFetchResult(
                html="",
                http_status=0,
                byte_size=0,
                fetched_at=datetime.now(UTC),
                headers={},
                error=str(exc),
            )
        body = response.text
        return RawFetchResult(
            html=body,
            http_status=response.status_code,
            byte_size=len(response.content),
            fetched_at=datetime.now(UTC),
            headers=dict(response.headers.items()),
        )

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("httpx is required for HttpxCrawler") from exc
        self._client = httpx.AsyncClient()
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
