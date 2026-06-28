"""Notifier worker settings."""

from __future__ import annotations

from pydantic import Field

from lens_common.config import Settings

__all__ = ["NotifierSettings"]


class NotifierSettings(Settings):
    """Settings for the ``notifier_worker`` image."""

    notifier_prefetch: int = Field(
        default=8,
        ge=1,
        description="RabbitMQ prefetch count (QoS) for the notifier consumer.",
    )
    notifier_poll_seconds: float = Field(
        default=1.0,
        gt=0,
        description="How often the outbox relay drains the outbox table.",
    )
    notifier_outbox_batch_size: int = Field(
        default=100,
        ge=1,
        description="Maximum number of outbox rows the relay publishes per tick.",
    )
    encryption_key: str | None = Field(
        default=None,
        description=("Fernet key (URL-safe base64 32-byte) used to encrypt channel Apprise URLs at rest."),
    )
    database_url: str | None = Field(default=None)
    rabbitmq_url: str | None = Field(default=None)
    redis_url: str | None = Field(default=None)
    blob_root: str | None = Field(default=None)
    notify_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Max retry attempts per notification before DLQ.",
    )
    notify_retry_base_seconds: float = Field(
        default=5.0,
        ge=1.0,
        description="Base seconds for exponential backoff for notifications.",
    )
    per_channel_max_rate: int = Field(
        default=10,
        ge=1,
        description="Max notification sends per second per channel.",
    )
