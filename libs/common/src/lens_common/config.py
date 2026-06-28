"""Typed configuration base for every lens app.

Each app extends :class:`Settings` with its own subset of fields; the shared
base loads the bootstrap env vars that every role needs. The implementation
uses ``pydantic-settings`` so values can come from env, ``.env``, or process
arguments with fail-fast validation.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = [
    "AppRole",
    "LogFormat",
    "Settings",
    "load_settings",
]


class AppRole(StrEnum):
    """The role of the running instance; drives which services start up."""

    API = "api"
    SCHEDULER = "scheduler"
    CRAWLER = "crawler"
    NOTIFIER = "notifier"
    AI = "ai"
    CLI = "cli"


class LogFormat(StrEnum):
    """Output format for the structured logger."""

    JSON = "json"
    CONSOLE = "console"


class Settings(BaseSettings):
    """Shared base settings for every lens app.

    Apps subclass this and add their own fields. The base holds the
    bootstrap-tier variables needed by any role.
    """

    model_config = SettingsConfigDict(
        env_prefix="LENS_",
        env_file=None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    app_role: AppRole = Field(
        default=AppRole.API,
        description="Role of the running instance; selects which services start.",
    )

    log_level: str = Field(
        default="INFO",
        description="Standard log level (DEBUG/INFO/WARNING/ERROR/CRITICAL).",
    )
    log_format: LogFormat = Field(
        default=LogFormat.JSON,
        description="Log output format (json or console).",
    )

    global_min_interval: int = Field(
        default=300,
        ge=1,
        description="Floor (seconds) for Url.interval_seconds.",
    )
    max_snapshots: int = Field(
        default=25,
        ge=1,
        description="Per-URL snapshot retention cap.",
    )

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in logging._nameToLevel:
            raise ValueError(f"invalid log level: {value!r}")
        return normalized

    def env_mapping(self) -> dict[str, str]:
        """Return the field -> env-var mapping for this settings class."""
        prefix = type(self).model_config.get("env_prefix", "") or ""
        return {name: f"{prefix}{name.upper()}" for name in type(self).model_fields}


def load_settings[S: Settings](cls: type[S], env_file: Path | None = None) -> S:
    """Load settings with fail-fast validation.

    Wraps the construction so :class:`pydantic.ValidationError` is converted
    to a clear, single-line error message suitable for startup logs.
    """
    try:
        return cls(_env_file=env_file)  # pyright: ignore[reportCallIssue]
    except ValidationError as exc:
        joined = "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors())
        raise RuntimeError(f"invalid configuration: {joined}") from exc
