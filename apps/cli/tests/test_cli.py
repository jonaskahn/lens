"""CLI command tests (Typer with in-memory UoW)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from _cli_fakes import InMemoryUnitOfWork, reset_in_memory_store
from typer.testing import CliRunner

from lens_cli.commands import build_app
from lens_cli.composition import build_cli_composition


@pytest.fixture(autouse=True)
def _clear_store() -> None:
    reset_in_memory_store()


def _app() -> object:
    composition = build_cli_composition(InMemoryUnitOfWork)
    return build_app(composition)


def test_given_setup_json_when_import_then_creates_entities() -> None:
    runner = CliRunner()
    app = _app()
    setup = {
        "version": 1,
        "domains": [
            {
                "host": "shop.example.com",
                "categories": [
                    {
                        "name": "products",
                        "urls": [
                            {
                                "address": "https://shop.example.com/p/1",
                                "interval_seconds": 600,
                            },
                        ],
                    },
                ],
            },
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(setup, f)
        path = f.name
    result = runner.invoke(app, ["import", path])
    assert result.exit_code == 0, result.stdout
    list_result = runner.invoke(app, ["url", "list", "--format", "json"])
    assert list_result.exit_code == 0
    body = json.loads(list_result.stdout)
    assert len(body) == 1
    assert body[0]["address"] == "https://shop.example.com/p/1"


def test_given_yaml_when_import_then_parses() -> None:
    runner = CliRunner()
    app = _app()
    yaml_body = (
        "version: 1\n"
        "domains:\n"
        "  - host: news.example.com\n"
        "    categories:\n"
        "      - name: articles\n"
        "        urls:\n"
        "          - address: https://news.example.com/a/1\n"
        "            interval_seconds: 900\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_body)
        path = f.name
    result = runner.invoke(app, ["import", path])
    assert result.exit_code == 0, result.stdout
    list_result = runner.invoke(app, ["url", "list", "--format", "json"])
    assert list_result.exit_code == 0
    body = json.loads(list_result.stdout)
    assert len(body) == 1
    assert body[0]["address"] == "https://news.example.com/a/1"


def test_given_csv_when_import_then_parses() -> None:
    runner = CliRunner()
    app = _app()
    csv_body = (
        "domain_host,category_name,address,interval_seconds,enabled\n"
        "shop.example.com,products,https://shop.example.com/csv/1,600,true\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv_body)
        path = f.name
    result = runner.invoke(app, ["import", path])
    assert result.exit_code == 0, result.stdout
    list_result = runner.invoke(app, ["url", "list", "--format", "json"])
    body = json.loads(list_result.stdout)
    assert len(body) == 1
    assert body[0]["address"] == "https://shop.example.com/csv/1"


def test_given_setup_when_export_then_round_trip() -> None:
    runner = CliRunner()
    app = _app()
    add = runner.invoke(
        app,
        ["domain", "add", "--host", "example.com", "--display-name", "Example"],
    )
    assert add.exit_code == 0, add.stdout
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        out_path = f.name
    result = runner.invoke(app, ["export", "--out", out_path])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(Path(out_path).read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["domains"][0]["host"] == "example.com"


def test_given_on_conflict_replace_when_runs_then_accepted() -> None:
    runner = CliRunner()
    app = _app()
    setup = {
        "version": 1,
        "domains": [
            {
                "host": "shop.example.com",
                "categories": [
                    {
                        "name": "products",
                        "urls": [
                            {
                                "address": "https://shop.example.com/p/1",
                                "interval_seconds": 600,
                            },
                        ],
                    },
                ],
            },
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(setup, f)
        path = f.name
    first = runner.invoke(app, ["import", path])
    second = runner.invoke(app, ["import", "--on-conflict", "replace", path])
    assert first.exit_code == 0
    assert second.exit_code == 0, second.stdout


def test_given_domain_add_then_list_then_visible() -> None:
    runner = CliRunner()
    app = _app()
    add = runner.invoke(
        app,
        ["domain", "add", "--host", "example.com", "--display-name", "Example"],
    )
    assert add.exit_code == 0, add.stdout
    list_result = runner.invoke(app, ["domain", "list", "--format", "json"])
    body = json.loads(list_result.stdout)
    assert len(body) == 1
    assert body[0]["host"] == "example.com"


def test_given_domain_and_category_when_url_add_with_category_then_succeeds() -> None:
    runner = CliRunner()
    app = _app()
    runner.invoke(app, ["domain", "add", "--host", "example.com"])
    runner.invoke(
        app,
        ["category", "add", "--domain", "example.com", "--name", "blog"],
    )
    result = runner.invoke(
        app,
        [
            "url",
            "add",
            "--domain",
            "example.com",
            "--address",
            "https://example.com/post/1",
            "--category",
            "blog",
        ],
    )
    assert result.exit_code == 0, result.stdout


def test_given_domain_with_categories_when_category_list_with_domain_then_shows_categories() -> None:
    runner = CliRunner()
    app = _app()
    runner.invoke(app, ["domain", "add", "--host", "example.com"])
    runner.invoke(
        app,
        ["category", "add", "--domain", "example.com", "--name", "blog"],
    )
    result = runner.invoke(
        app,
        ["category", "list", "--domain", "example.com", "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout
    body = json.loads(result.stdout)
    assert len(body) == 1
    assert body[0]["name"] == "blog"
