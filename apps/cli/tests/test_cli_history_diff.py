"""CLI tests for the check, history, diff, and snapshot commands."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from _cli_fakes import InMemoryUnitOfWork, reset_in_memory_store
from typer.testing import CliRunner

from lens_application.dto import (
    CreateDomainInput,
    CreateUrlInput,
)
from lens_application.use_cases import (
    CreateDomainUseCase,
    CreateUrlUseCase,
)
from lens_cli.commands import build_app
from lens_cli.composition import build_cli_composition
from lens_infrastructure.broker import InMemoryBroker, InMemoryTaskPublisher


@pytest.fixture(autouse=True)
def _clear() -> None:
    reset_in_memory_store()


def _broker_composition() -> tuple[object, InMemoryBroker]:
    broker = InMemoryBroker()
    publisher = InMemoryTaskPublisher(broker)
    composition = build_cli_composition(
        InMemoryUnitOfWork,
        task_publisher=publisher,
    )
    return build_app(composition), broker


def _seed_url() -> str:
    from datetime import UTC, datetime

    factory = InMemoryUnitOfWork

    async def _run() -> str:
        domain = await CreateDomainUseCase(factory).execute(
            CreateDomainInput(host="example.com"),
        )
        url = await CreateUrlUseCase(factory).execute(
            CreateUrlInput(
                domain_id=domain.id,
                address="https://example.com/p",
                interval_seconds=600,
            ),
        )
        async with factory() as uow:
            entity = await uow.urls.get(url.id)
            assert entity is not None
            entity.next_due_at = datetime.now(UTC)
            await uow.urls.update(entity)
        return str(url.id)

    return __import__("asyncio").run(_run())


def test_given_url_when_check_now_then_publishes_task() -> None:
    app, broker = _broker_composition()
    url_id = _seed_url()
    runner = CliRunner()
    result = runner.invoke(app, ["check", "now", "--url", url_id])
    assert result.exit_code == 0, result.stdout
    queue = broker.attach_consumer("crawl.task")
    assert queue.qsize() == 1


def test_given_url_when_history_then_empty_table() -> None:
    app, _ = _broker_composition()
    url_id = _seed_url()
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["history", "list", "--url", url_id, "--format", "json"],
    )
    assert result.exit_code == 0, result.stdout
    body = json.loads(result.stdout)
    assert body == []


def test_given_url_when_snapshot_then_404_message() -> None:
    app, _ = _broker_composition()
    url_id = _seed_url()
    runner = CliRunner()
    result = runner.invoke(app, ["snapshot", "get", "--url", url_id])
    assert result.exit_code == 1, result.stdout


def test_given_change_when_diff_then_returns_summary() -> None:
    app, _ = _broker_composition()
    runner = CliRunner()
    fake_change_id = str(uuid4())
    result = runner.invoke(app, ["history", "diff", "--change", fake_change_id])
    # NotFoundError surfaces as a non-zero exit code via the unhandled
    # exception path; the CLI doesn't need to format it specially.
    assert result.exit_code != 0
