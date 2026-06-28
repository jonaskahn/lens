"""Crawler-worker settings."""

from __future__ import annotations

from pydantic import Field

from lens_common.config import Settings

__all__ = ["CrawlerWorkerSettings"]


class CrawlerWorkerSettings(Settings):
    """Settings for the ``crawler_worker`` image."""

    crawler_concurrency: int = Field(
        default=4,
        ge=1,
        description="Max concurrent crawl tasks per worker.",
    )
    crawler_prefetch: int = Field(
        default=4,
        ge=1,
        description="RabbitMQ prefetch count (QoS).",
    )
    crawler_lease_ttl_seconds: int = Field(
        default=120,
        ge=10,
        description="Per-URL lease TTL in seconds.",
    )
    database_url: str | None = Field(default=None)
    rabbitmq_url: str | None = Field(default=None)
    blob_root: str | None = Field(
        default=None,
        description="Local FS root for blob storage (local backend).",
    )
    crawl_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Max retry attempts per crawl before DLQ.",
    )
    crawl_retry_base_seconds: float = Field(
        default=5.0,
        ge=1.0,
        description="Base seconds for exponential backoff.",
    )
    politeness_min_delay_seconds: float = Field(
        default=5.0,
        ge=0.0,
        description="Minimum seconds between crawls to the same domain.",
    )
    politeness_max_rate: int = Field(
        default=10,
        ge=1,
        description="Max requests per second to a single domain.",
    )
    redis_url: str | None = Field(
        default=None,
        description="Redis URL for idempotency, throttle, and locks.",
    )
