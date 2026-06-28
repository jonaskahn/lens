"""CLI tests for the channel, binding, and test-notify commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest
from _cli_fakes import InMemoryUnitOfWork, reset_in_memory_store
from typer.testing import CliRunner

from lens_application.pipeline import (
    RenderedMessage,
    SendResult,
)
from lens_cli.commands import build_app
from lens_cli.composition import build_cli_composition
from lens_domain.entities import Channel


@dataclass
class _CapturingRenderer:
    template: str = "change.txt"

    def render(
        self,
        *,
        template_name: str,
        context: dict[str, Any],
    ) -> RenderedMessage:
        return RenderedMessage(
            subject="[lens] test",
            body=f"template={template_name}",
            template=template_name,
        )


@dataclass
class _CapturingNotifier:
    sent: list[dict[str, Any]] = field(default_factory=list)
    fail: bool = False

    async def send(
        self,
        *,
        channel_kind: str,
        apprise_url: str,
        message: RenderedMessage,
    ) -> SendResult:
        self.sent.append(
            {
                "channel_kind": channel_kind,
                "apprise_url": apprise_url,
                "subject": message.subject,
                "body": message.body,
            },
        )
        if self.fail:
            return SendResult(success=False, error="simulated")
        return SendResult(success=True)


@dataclass
class _StaticSecrets:
    def apprise_url_for(self, channel: Channel) -> str:
        return f"json://{channel.id}/notify"


def _app() -> Any:
    composition = build_cli_composition(InMemoryUnitOfWork)
    return build_app(composition)


def _app_with_test_notify(notifier: _CapturingNotifier) -> Any:
    composition = build_cli_composition(
        InMemoryUnitOfWork,
        renderer=_CapturingRenderer(),
        notifier=notifier,
        secrets=_StaticSecrets(),
    )
    return build_app(composition)


@pytest.fixture(autouse=True)
def _clear_store() -> None:
    reset_in_memory_store()


# ---------------------------------------------------------------------------
# channel add / list / rm / enable / disable
# ---------------------------------------------------------------------------


def test_given_channel_add_when_invoked_then_channel_is_created() -> None:
    runner = CliRunner()
    result = runner.invoke(
        _app(),
        [
            "channel",
            "add",
            "--name",
            "ops",
            "--kind",
            "webhook",
            "--url",
            "json://localhost/ops",
        ],
    )
    assert result.exit_code == 0, result.stdout
    list_result = runner.invoke(_app(), ["channel", "list", "--format", "json"])
    assert list_result.exit_code == 0
    body = list_result.stdout
    assert "ops" in body
    assert "json://localhost/ops" not in body  # URL must never be printed


def test_given_channel_add_with_disable_when_invoked_then_created_disabled() -> None:
    runner = CliRunner()
    add_result = runner.invoke(
        _app(),
        [
            "channel",
            "add",
            "--name",
            "ops",
            "--kind",
            "email",
            "--url",
            "mailto://user:pass@host",
            "--disable",
        ],
    )
    assert add_result.exit_code == 0, add_result.stdout
    list_result = runner.invoke(_app(), ["channel", "list", "--format", "json"])
    body = list_result.stdout
    assert "false" in body  # enabled == false


def test_given_channel_list_when_no_channels_then_empty_table() -> None:
    runner = CliRunner()
    result = runner.invoke(_app(), ["channel", "list"])
    assert result.exit_code == 0


def test_given_existing_channel_when_rm_then_removed() -> None:
    runner = CliRunner()
    add = runner.invoke(
        _app(),
        [
            "channel",
            "add",
            "--name",
            "ops",
            "--kind",
            "webhook",
            "--url",
            "json://localhost/ops",
        ],
    )
    assert add.exit_code == 0
    # Get id from list
    list_result = runner.invoke(_app(), ["channel", "list", "--format", "json"])
    import json

    items = json.loads(list_result.stdout)
    channel_id = items[0]["id"]
    rm = runner.invoke(_app(), ["channel", "rm", channel_id])
    assert rm.exit_code == 0
    list_after = runner.invoke(_app(), ["channel", "list", "--format", "json"])
    assert list_after.stdout.strip() == "[]"


def test_given_existing_channel_when_disable_then_enabled_false() -> None:
    runner = CliRunner()
    runner.invoke(
        _app(),
        [
            "channel",
            "add",
            "--name",
            "ops",
            "--kind",
            "webhook",
            "--url",
            "json://localhost/ops",
        ],
    )
    list_result = runner.invoke(_app(), ["channel", "list", "--format", "json"])
    import json

    items = json.loads(list_result.stdout)
    channel_id = items[0]["id"]
    disable = runner.invoke(_app(), ["channel", "disable", channel_id])
    assert disable.exit_code == 0
    after = runner.invoke(_app(), ["channel", "list", "--format", "json"])
    body = json.loads(after.stdout)
    assert body[0]["enabled"] is False


def test_given_disabled_channel_when_enable_then_enabled_true() -> None:
    runner = CliRunner()
    runner.invoke(
        _app(),
        [
            "channel",
            "add",
            "--name",
            "ops",
            "--kind",
            "webhook",
            "--url",
            "json://localhost/ops",
            "--disable",
        ],
    )
    list_result = runner.invoke(_app(), ["channel", "list", "--format", "json"])
    import json

    items = json.loads(list_result.stdout)
    channel_id = items[0]["id"]
    enable = runner.invoke(_app(), ["channel", "enable", channel_id])
    assert enable.exit_code == 0
    after = runner.invoke(_app(), ["channel", "list", "--format", "json"])
    body = json.loads(after.stdout)
    assert body[0]["enabled"] is True


# ---------------------------------------------------------------------------
# binding add / list / update / rm
# ---------------------------------------------------------------------------


def _add_channel(runner: CliRunner, name: str) -> str:
    add = runner.invoke(
        _app(),
        [
            "channel",
            "add",
            "--name",
            name,
            "--kind",
            "webhook",
            "--url",
            f"json://localhost/{name}",
        ],
    )
    assert add.exit_code == 0, add.stdout
    list_result = runner.invoke(_app(), ["channel", "list", "--format", "json"])
    import json

    items = json.loads(list_result.stdout)
    return next(item["id"] for item in items if item["name"] == name)


def test_given_binding_add_global_when_invoked_then_created() -> None:
    runner = CliRunner()
    channel_id = _add_channel(runner, "ops")
    result = runner.invoke(
        _app(),
        [
            "binding",
            "add",
            "--channel",
            channel_id,
            "--scope",
            "global",
            "--on-change",
        ],
    )
    assert result.exit_code == 0, result.stdout
    list_result = runner.invoke(_app(), ["binding", "list", "--format", "json"])
    import json

    bindings = json.loads(list_result.stdout)
    assert len(bindings) == 1
    assert bindings[0]["scope"] == "global"
    assert bindings[0]["on_change"] is True


def test_given_binding_add_with_scope_id_when_invoked_then_created() -> None:
    runner = CliRunner()
    import asyncio

    from lens_application.dto import CreateDomainInput
    from lens_application.use_cases import CreateDomainUseCase

    domain_dto = asyncio.run(
        CreateDomainUseCase(InMemoryUnitOfWork).execute(
            CreateDomainInput(host="shop.example.com"),
        ),
    )
    channel_id = _add_channel(runner, "ops")
    result = runner.invoke(
        _app(),
        [
            "binding",
            "add",
            "--channel",
            channel_id,
            "--scope",
            "domain",
            "--scope-id",
            str(domain_dto.id),
        ],
    )
    assert result.exit_code == 0, result.stdout
    list_result = runner.invoke(_app(), ["binding", "list", "--scope", "domain", "--format", "json"])
    import json

    bindings = json.loads(list_result.stdout)
    assert len(bindings) == 1
    assert bindings[0]["scope"] == "domain"
    assert bindings[0]["scope_id"] == str(domain_dto.id)


def test_given_binding_update_when_invoked_then_triggers_updated() -> None:
    runner = CliRunner()
    channel_id = _add_channel(runner, "ops")
    add = runner.invoke(
        _app(),
        [
            "binding",
            "add",
            "--channel",
            channel_id,
            "--scope",
            "global",
        ],
    )
    assert add.exit_code == 0
    list_result = runner.invoke(_app(), ["binding", "list", "--format", "json"])
    import json

    bindings = json.loads(list_result.stdout)
    binding_id = bindings[0]["id"]
    update = runner.invoke(
        _app(),
        [
            "binding",
            "update",
            binding_id,
            "--on-error",
            "--no-on-change",
        ],
    )
    assert update.exit_code == 0
    after = runner.invoke(_app(), ["binding", "list", "--format", "json"])
    body = json.loads(after.stdout)
    assert body[0]["on_change"] is False
    assert body[0]["on_error"] is True


def test_given_binding_rm_when_invoked_then_removed() -> None:
    runner = CliRunner()
    channel_id = _add_channel(runner, "ops")
    runner.invoke(
        _app(),
        [
            "binding",
            "add",
            "--channel",
            channel_id,
            "--scope",
            "global",
        ],
    )
    list_result = runner.invoke(_app(), ["binding", "list", "--format", "json"])
    import json

    bindings = json.loads(list_result.stdout)
    binding_id = bindings[0]["id"]
    rm = runner.invoke(_app(), ["binding", "rm", binding_id])
    assert rm.exit_code == 0
    after = runner.invoke(_app(), ["binding", "list", "--format", "json"])
    assert after.stdout.strip() == "[]"


# ---------------------------------------------------------------------------
# test-notify
# ---------------------------------------------------------------------------


def test_given_channel_when_test_notify_then_sends() -> None:
    runner = CliRunner()
    notifier = _CapturingNotifier()
    composition = build_cli_composition(
        InMemoryUnitOfWork,
        renderer=_CapturingRenderer(),
        notifier=notifier,
        secrets=_StaticSecrets(),
    )
    app = build_app(composition)
    add = runner.invoke(
        app,
        [
            "channel",
            "add",
            "--name",
            "ops",
            "--kind",
            "webhook",
            "--url",
            "json://localhost/ops",
        ],
    )
    assert add.exit_code == 0
    list_result = runner.invoke(app, ["channel", "list", "--format", "json"])
    import json

    items = json.loads(list_result.stdout)
    channel_id = items[0]["id"]
    test = runner.invoke(app, ["notify", "test", "--channel", channel_id])
    assert test.exit_code == 0, test.stdout
    assert len(notifier.sent) == 1
    assert notifier.sent[0]["apprise_url"] == f"json://{channel_id}/notify"


def test_given_send_failure_when_test_notify_then_nonzero_exit() -> None:
    runner = CliRunner()
    notifier = _CapturingNotifier(fail=True)
    composition = build_cli_composition(
        InMemoryUnitOfWork,
        renderer=_CapturingRenderer(),
        notifier=notifier,
        secrets=_StaticSecrets(),
    )
    app = build_app(composition)
    runner.invoke(
        app,
        [
            "channel",
            "add",
            "--name",
            "ops",
            "--kind",
            "webhook",
            "--url",
            "json://localhost/ops",
        ],
    )
    list_result = runner.invoke(app, ["channel", "list", "--format", "json"])
    import json

    items = json.loads(list_result.stdout)
    channel_id = items[0]["id"]
    test = runner.invoke(app, ["notify", "test", "--channel", channel_id])
    assert test.exit_code != 0
    assert "simulated" in test.stdout


def test_given_no_test_notify_when_invoked_then_exit_1() -> None:
    runner = CliRunner()
    add = runner.invoke(
        _app(),
        [
            "channel",
            "add",
            "--name",
            "ops",
            "--kind",
            "webhook",
            "--url",
            "json://localhost/ops",
        ],
    )
    assert add.exit_code == 0
    list_result = runner.invoke(_app(), ["channel", "list", "--format", "json"])
    import json

    items = json.loads(list_result.stdout)
    channel_id = items[0]["id"]
    test = runner.invoke(_app(), ["notify", "test", "--channel", channel_id])
    assert test.exit_code != 0
    assert "test-notify unavailable" in test.stdout


def test_given_missing_channel_when_test_notify_then_nonzero_exit() -> None:
    runner = CliRunner()
    notifier = _CapturingNotifier()
    app = _app_with_test_notify(notifier)
    test = runner.invoke(app, ["notify", "test", "--channel", str(uuid4())])
    assert test.exit_code != 0


def test_given_no_channels_when_channel_list_then_empty() -> None:
    runner = CliRunner()
    result = runner.invoke(_app(), ["channel", "list", "--format", "json"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "[]"
