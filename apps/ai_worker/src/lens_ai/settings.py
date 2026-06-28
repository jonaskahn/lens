"""AI worker settings (behind AI_ENABLED)."""

from __future__ import annotations

from pydantic import Field

from lens_common.config import Settings

__all__ = ["AIWorkerSettings"]


class AIWorkerSettings(Settings):
    """Settings for the ``ai_worker`` image."""

    ai_enabled: bool = Field(
        default=False,
        description="Master switch (must also be true on crawler_worker).",
    )
    ai_prefetch: int = Field(
        default=2,
        ge=1,
        description="RabbitMQ prefetch count for enrichment tasks.",
    )
    llm_backend: str = Field(
        default="vllm",
        description="'vllm', 'openai_compatible', or 'api'.",
    )
    llm_endpoint: str = Field(
        default="http://localhost:8000/v1",
        description="OpenAI-compatible /v1 base URL.",
    )
    llm_model: str = Field(
        default="Qwen2.5-7B-Instruct",
        description="Classifier model id.",
    )
    llm_timeout_seconds: float = Field(
        default=30.0,
        ge=5.0,
        description="LLM request timeout.",
    )
    enrich_max_attempts: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Retry cap before enrich.tasks.dlq.",
    )
    enrich_retry_base_seconds: float = Field(
        default=5.0,
        ge=1.0,
        description="Base seconds for exponential backoff.",
    )
    database_url: str | None = Field(default=None)
    rabbitmq_url: str | None = Field(default=None)
    redis_url: str | None = Field(default=None)
