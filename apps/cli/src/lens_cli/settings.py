"""CLI settings: same bootstrap env vars as the API role."""

from __future__ import annotations

from pydantic import Field

from lens_common.config import Settings

__all__ = ["CliSettings"]


class CliSettings(Settings):
    """Settings for the ``cli`` image (operator commands)."""

    database_url: str | None = Field(
        default=None,
        description="Postgres connection URL (e.g. postgresql+psycopg2://...).",
    )
