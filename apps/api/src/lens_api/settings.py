"""API settings: bootstrap env vars + per-app overrides."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from lens_common.config import Settings

__all__ = ["ApiSettings"]


class ApiSettings(Settings):
    """Settings for the ``api`` image (FastAPI + uvicorn)."""

    model_config = SettingsConfigDict(
        env_prefix="LENS_",
        env_file=None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_rate_limit: int = Field(
        default=100,
        ge=1,
        description="Max API requests per key per window.",
    )
    api_rate_window: int = Field(
        default=60,
        ge=1,
        description="Rate limit window in seconds.",
    )
    api_max_page_size: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="Maximum page size for list endpoints.",
    )
