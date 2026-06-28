"""Settings loading: env precedence, fail-fast, per-app extension."""

from __future__ import annotations

import pytest
from pydantic import Field

from lens_common.config import AppRole, LogFormat, Settings, load_settings


class SampleSettings(Settings):
    """Settings subclass with custom fields used in tests."""

    custom_str: str = Field(default="default-value", description="Custom test field.")
    custom_int: int = Field(default=42, ge=1, le=100)


def test_given_env_file_when_load_settings_then_values_override_defaults(
    tmp_path,
    monkeypatch,
) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text(
        "LENS_LOG_LEVEL=DEBUG\nLENS_CUSTOM_STR=from-env\n",
        encoding="utf-8",
    )
    for var in (
        "LENS_LOG_LEVEL",
        "LENS_CUSTOM_STR",
        "LENS_CUSTOM_INT",
        "LENS_LOG_FORMAT",
        "LENS_APP_ROLE",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = load_settings(SampleSettings, env_file=env_file)

    assert settings.log_level == "DEBUG"
    assert settings.custom_str == "from-env"
    assert settings.custom_int == 42
    assert settings.app_role == AppRole.API
    assert settings.log_format == LogFormat.JSON


def test_given_invalid_log_level_when_load_settings_then_runtime_error(tmp_path) -> None:
    env_file = tmp_path / "test.env"
    env_file.write_text("LENS_LOG_LEVEL=NOPE\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="invalid configuration"):
        load_settings(SampleSettings, env_file=env_file)


def test_given_settings_when_log_level_set_then_normalised_to_upper() -> None:
    settings = SampleSettings(log_level="debug")
    assert settings.log_level == "DEBUG"


def test_given_settings_when_env_mapping_then_keys_have_lens_prefix() -> None:
    mapping = SampleSettings().env_mapping()
    assert mapping["custom_str"] == "LENS_CUSTOM_STR"
    assert mapping["log_level"] == "LENS_LOG_LEVEL"


def test_given_settings_when_no_env_file_then_defaults_apply() -> None:
    settings = SampleSettings()
    assert settings.log_level == "INFO"
    assert settings.app_role == AppRole.API
    assert settings.log_format == LogFormat.JSON
    assert settings.global_min_interval == 300
    assert settings.max_snapshots == 25
