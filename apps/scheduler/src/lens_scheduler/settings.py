"""Scheduler settings: shared env vars + scheduler-specific knobs."""

from __future__ import annotations

from pydantic import Field

from lens_common.config import Settings

__all__ = ["SchedulerSettings"]


class SchedulerSettings(Settings):
    """Settings for the ``scheduler`` image."""

    scheduler_tick_seconds: float = Field(
        default=10.0,
        gt=0.0,
        description="Seconds between scheduler ticks.",
    )
    scheduler_batch_size: int = Field(
        default=100,
        ge=1,
        description="Max URLs to claim per tick.",
    )
    database_url: str | None = Field(
        default=None,
        description="Postgres DSN; required in production deployments.",
    )
    rabbitmq_url: str | None = Field(
        default=None,
        description="RabbitMQ URL; required in production deployments.",
    )
    max_queue_depth: int = Field(
        default=1000,
        ge=0,
        description="Max crawl.tasks queue depth before backpressure engages.",
    )
    shard_id: int = Field(
        default=0,
        ge=0,
        description="Replica id for hash-based sharding.",
    )
    shard_count: int = Field(
        default=1,
        ge=1,
        description="Total number of scheduler replicas for hash-based sharding.",
    )
    leader_lock_key: str = Field(
        default="lens:scheduler:leader",
        description="Redis key for leader election lock.",
    )
