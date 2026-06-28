"""CLI commands (Typer)."""

from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final, cast
from uuid import UUID

import typer
import yaml  # type: ignore[import-untyped]
from rich.console import Console
from rich.table import Table

from lens_application.dto import (
    ConflictPolicy,
    CreateCategoryInput,
    CreateChannelBindingInput,
    CreateChannelInput,
    CreateDomainInput,
    CreateUrlInput,
    SetupDto,
    TriggerCheckInput,
    UpdateChannelBindingInput,
    UpdateChannelInput,
)
from lens_cli.composition import CliComposition

DEFAULT_URL_INTERVAL: Final[int] = 3600

__all__ = ["app", "build_app"]


def _run(coro: Any) -> Any:
    """Drive an async coroutine to completion from a sync Typer command."""
    return asyncio.run(coro)


console = Console()
app = typer.Typer(
    name="lens",
    help="Operator CLI for lens (import/export setups, manage entities, migrate).",
    no_args_is_help=True,
)

domain_app = typer.Typer(help="Domain commands.")
category_app = typer.Typer(help="Category commands.")
url_app = typer.Typer(help="Url commands.")
app.add_typer(domain_app, name="domain")
app.add_typer(category_app, name="category")
app.add_typer(url_app, name="url")

check_app = typer.Typer(help="Manual check-now commands.")
history_app = typer.Typer(help="History & diff commands.")
snapshot_app = typer.Typer(help="Snapshot commands.")
app.add_typer(check_app, name="check")
app.add_typer(history_app, name="history")
app.add_typer(snapshot_app, name="snapshot")


channel_app = typer.Typer(help="Notification channel commands.")
binding_app = typer.Typer(help="Channel binding commands.")
notify_app = typer.Typer(help="Notification commands.")
app.add_typer(channel_app, name="channel")
app.add_typer(binding_app, name="binding")
app.add_typer(notify_app, name="notify")


class OutputFormat(StrEnum):
    TABLE = "table"
    JSON = "json"


@app.callback()
def _main_callback(
    fmt: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--format",
        help="Output format (table or json).",
    ),
) -> None:
    """Lens operator CLI — import/export setups, manage entities, migrate."""


def _read_setup(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in {".yaml", ".yml"}:
        return cast(dict[str, Any], yaml.safe_load(text) or {})
    if suffix == ".csv":
        return _csv_to_setup(text)
    return cast(dict[str, Any], json.loads(text or "{}"))


def _csv_to_setup(text: str) -> dict[str, Any]:
    reader = csv.DictReader(io.StringIO(text))
    setup: dict[str, Any] = {"version": 1, "domains": []}
    domains_by_host: dict[str, dict[str, Any]] = {}
    for row in reader:
        host = row.get("domain_host", "").strip()
        if not host:
            continue
        if host not in domains_by_host:
            domains_by_host[host] = {"host": host, "categories": []}
            setup["domains"].append(domains_by_host[host])
        domain = domains_by_host[host]
        cat_name = row.get("category_name", "").strip() or None
        category = next(
            (c for c in domain["categories"] if c.get("name") == cat_name),
            None,
        )
        if cat_name and category is None:
            category = {"name": cat_name, "urls": []}
            domain["categories"].append(category)
        target = category or domain
        target.setdefault("urls", []).append(
            {
                "address": row.get("address", ""),
                "interval_seconds": int(row.get("interval_seconds", 300)),
                "enabled": row.get("enabled", "true").lower() == "true",
            },
        )
    return setup


def _write_setup(path: Path, payload: dict[str, Any]) -> None:
    suffix = path.suffix.lower()
    text = yaml.safe_dump(payload, sort_keys=False) if suffix in {".yaml", ".yml"} else json.dumps(payload, indent=2)
    path.write_text(text, encoding="utf-8")


def _on_conflict(value: str) -> ConflictPolicy:
    try:
        return ConflictPolicy(value)
    except ValueError as exc:
        raise typer.BadParameter(f"invalid --on-conflict: {value}") from exc


def build_app(composition: CliComposition) -> typer.Typer:
    """Build the Typer app wired to ``composition``."""

    @app.command("import")
    def import_cmd(
        file: Path = typer.Argument(..., help="Path to the setup file (json/yaml/csv)."),
        on_conflict: str = typer.Option("skip", "--on-conflict", help="skip|merge|replace"),
    ) -> None:
        from lens_cli.settings import CliSettings

        settings = CliSettings()
        payload = _read_setup(file)
        setup = SetupDto.model_validate(payload)
        result = _run(
            composition.import_setup.execute(
                {
                    "setup": setup,
                    "on_conflict": _on_conflict(on_conflict),
                    "global_min_interval": settings.global_min_interval,
                },
            ),
        )
        console.print(
            f"[green]created={result.created}[/] updated={result.updated} "
            f"skipped={result.skipped} errors={len(result.errors)}",
        )
        for err in result.errors:
            console.print(f"  [red]{err}[/]")

    @app.command("export")
    def export_cmd(
        out: Path = typer.Option(Path("-"), "--out", help="Output file or - for stdout."),
        domain: str | None = typer.Option(None, "--domain", help="Domain host to export."),
    ) -> None:
        result = _run(composition.export_setup.execute({"domain_host": domain}))
        payload = result.setup.model_dump(mode="json")
        if str(out) == "-":
            console.print(json.dumps(payload, indent=2))
        else:
            _write_setup(out, payload)
            console.print(f"[green]wrote {out}[/]")

    @app.command("migrate")
    def migrate_cmd() -> None:
        from pathlib import Path

        from alembic import command as alembic_command
        from alembic.config import Config

        from lens_cli.settings import CliSettings

        settings = CliSettings()
        if settings.database_url is None:
            console.print("[red]LENS_DATABASE_URL is required for migration[/]")
            raise typer.Exit(code=1)

        candidates = [
            Path.cwd() / "alembic.ini",
            Path.cwd() / "libs" / "infrastructure" / "migrations" / "alembic.ini",
        ]
        try:
            import lens_infrastructure

            pkg_dir = Path(lens_infrastructure.__file__).resolve().parent.parent
            candidates.append(pkg_dir / "migrations" / "alembic.ini")
        except ImportError:
            pass

        config_path: str | None = None
        for candidate in candidates:
            if candidate.exists():
                config_path = str(candidate)
                break

        if config_path is None:
            console.print(
                "[red]Could not find alembic.ini — pass --config PATH or set ALEMBIC_CONFIG[/]",
            )
            raise typer.Exit(code=1)

        console.print(f"Running migrations (config: {config_path})")
        try:
            alembic_cfg = Config(config_path)
            alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
            alembic_command.upgrade(alembic_cfg, "head")
        except Exception as exc:
            console.print(f"[red]Migration failed: {exc}[/]")
            raise typer.Exit(code=1) from exc
        console.print("[green]Migrations applied successfully[/]")

    @domain_app.command("add")
    def domain_add(
        host: str = typer.Option(..., "--host"),
        display_name: str | None = typer.Option(None, "--display-name"),
    ) -> None:
        dto = _run(
            composition.create_domain.execute(
                CreateDomainInput(host=host, display_name=display_name),
            ),
        )
        console.print(f"created domain [bold]{dto.host}[/] id={dto.id}")

    @domain_app.command("list")
    def domain_list(
        fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format"),
    ) -> None:
        result = _run(composition.list_domains.execute({}))
        if fmt == OutputFormat.JSON:
            console.print_json(data=[dto.model_dump(mode="json") for dto in result.items])
            return
        table = Table("id", "host", "display_name", "enabled")
        for dto in result.items:
            table.add_row(str(dto.id), dto.host, dto.display_name or "", str(dto.enabled))
        console.print(table)

    @domain_app.command("rm")
    def domain_rm(host: str = typer.Argument(...)) -> None:
        existing = _run(composition.get_domain.execute(host))
        _run(composition.delete_domain.execute(existing.id))
        console.print(f"removed domain [bold]{host}[/]")

    @url_app.command("add")
    def url_add(
        domain: str = typer.Option(..., "--domain"),
        address: str = typer.Option(..., "--address"),
        interval: int = typer.Option(DEFAULT_URL_INTERVAL, "--interval"),
        category: str | None = typer.Option(None, "--category"),
    ) -> None:
        domain_dto = _run(composition.get_domain.execute(domain))

        category_id = None
        if category is not None:
            categories = _run(
                composition.list_categories.execute({"domain_id": domain_dto.id}),
            )
            cat = next((c for c in categories.items if c.name == category), None)
            if cat is None:
                console.print(f"[red]category {category!r} not found[/]")
                raise typer.Exit(code=1)
            category_id = cat.id
        dto = _run(
            composition.create_url.execute(
                CreateUrlInput(
                    domain_id=domain_dto.id,
                    address=address,
                    interval_seconds=interval,
                    category_id=category_id,
                ),
            ),
        )
        console.print(f"created url [bold]{dto.address}[/] id={dto.id}")

    @url_app.command("list")
    def url_list(
        domain: str | None = typer.Option(None, "--domain"),
        fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format"),
    ) -> None:
        params: dict[str, Any] = {}
        if domain is not None:
            domain_dto = _run(composition.get_domain.execute(domain))
            params["domain_id"] = domain_dto.id
        result = _run(composition.list_urls.execute(params))
        if fmt == OutputFormat.JSON:
            console.print_json(data=[dto.model_dump(mode="json") for dto in result.items])
            return
        table = Table("id", "domain_id", "address", "status", "interval_s")
        for dto in result.items:
            table.add_row(
                str(dto.id),
                str(dto.domain_id),
                dto.address,
                dto.status,
                str(dto.interval_seconds),
            )
        console.print(table)

    @url_app.command("rm")
    def url_rm(url_id: str = typer.Argument(...)) -> None:
        _run(composition.delete_url.execute(UUID(url_id)))
        console.print(f"removed url id={url_id}")

    @category_app.command("add")
    def category_add(
        domain: str = typer.Option(..., "--domain"),
        name: str = typer.Option(..., "--name"),
        description: str | None = typer.Option(None, "--description"),
    ) -> None:
        domain_dto = _run(composition.get_domain.execute(domain))
        dto = _run(
            composition.create_category.execute(
                CreateCategoryInput(
                    domain_id=domain_dto.id,
                    name=name,
                    description=description,
                ),
            ),
        )
        console.print(f"created category [bold]{dto.name}[/] id={dto.id}")

    @category_app.command("list")
    def category_list(
        domain: str | None = typer.Option(None, "--domain"),
        fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format"),
    ) -> None:
        params: dict[str, Any] = {}
        if domain is not None:
            domain_dto = _run(composition.get_domain.execute(domain))
            params["domain_id"] = domain_dto.id
        result = _run(composition.list_categories.execute(params))
        if fmt == OutputFormat.JSON:
            console.print_json(data=[dto.model_dump(mode="json") for dto in result.items])
            return
        table = Table("id", "domain_id", "name", "description")
        for dto in result.items:
            table.add_row(str(dto.id), str(dto.domain_id), dto.name, dto.description or "")
        console.print(table)

    @check_app.command("now")
    def check_now_cmd(
        url: str | None = typer.Option(None, "--url", help="URL id to enqueue"),
        category: str | None = typer.Option(
            None,
            "--category",
            help="Category id to enqueue",
        ),
        domain: str | None = typer.Option(
            None,
            "--domain",
            help="Domain id to enqueue",
        ),
    ) -> None:
        input_dto = TriggerCheckInput(
            url_id=UUID(url) if url else None,
            category_id=UUID(category) if category else None,
            domain_id=UUID(domain) if domain else None,
        )
        result = _run(composition.trigger_check.execute(input_dto))
        console.print(
            f"[green]enqueued={result.enqueued}[/] url_ids={','.join(str(u) for u in result.url_ids)}",
        )

    @history_app.command("list")
    def history_cmd(
        url: str = typer.Option(..., "--url", help="URL id"),
        since: str | None = typer.Option(None, "--since"),
        limit: int = typer.Option(50, "--limit"),
        fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format"),
    ) -> None:
        since_dt: datetime | None = None
        if since is not None:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        result = _run(
            composition.list_changes.execute(
                {"url_id": UUID(url), "since": since_dt, "limit": limit},
            ),
        )
        if fmt == OutputFormat.JSON:
            console.print_json(
                data=[dto.model_dump(mode="json") for dto in result.items],
            )
            return
        table = Table("id", "url_id", "added", "removed", "significant", "created_at")
        for dto in result.items:
            table.add_row(
                str(dto.id),
                str(dto.url_id),
                str(dto.added_count),
                str(dto.removed_count),
                str(dto.significant),
                dto.created_at.isoformat(),
            )
        console.print(table)

    @history_app.command("diff")
    def diff_cmd(
        change: str = typer.Option(..., "--change", help="Change id"),
        out: Path = typer.Option(Path("-"), "--out"),
    ) -> None:
        payload = _run(composition.get_change_diff.execute(UUID(change)))
        text = json.dumps(payload, indent=2)
        if str(out) == "-":
            console.print(text)
        else:
            out.write_text(text, encoding="utf-8")
            console.print(f"[green]wrote {out}[/]")

    @snapshot_app.command("get")
    def snapshot_cmd(
        url: str = typer.Option(..., "--url", help="URL id"),
        out: Path = typer.Option(Path("-"), "--out"),
    ) -> None:
        try:
            snap = _run(composition.get_latest_snapshot.execute(UUID(url)))
        except Exception as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=1) from exc
        text = json.dumps(
            {
                "id": str(snap.id),
                "url_id": str(snap.url_id),
                "content_ref": snap.content_ref,
                "content_hash": snap.content_hash,
                "http_status": snap.http_status,
                "byte_size": snap.byte_size,
                "fetched_at": snap.fetched_at.isoformat(),
            },
            indent=2,
        )
        if str(out) == "-":
            console.print(text)
        else:
            out.write_text(text, encoding="utf-8")
            console.print(f"[green]wrote {out}[/]")

    @channel_app.command("add")
    def channel_add(
        name: str = typer.Option(..., "--name"),
        kind: str = typer.Option(..., "--kind", help="email|slack|discord|telegram|webhook"),
        url: str = typer.Option(..., "--url", help="Apprise URL (stored encrypted)"),
        disable: bool = typer.Option(False, "--disable", help="Create the channel disabled."),
    ) -> None:
        dto = _run(
            composition.create_channel.execute(
                CreateChannelInput(
                    name=name,
                    kind=kind,
                    apprise_url=url,
                    enabled=not disable,
                ),
            ),
        )
        console.print(
            f"created channel [bold]{dto.name}[/] id={dto.id} kind={dto.kind}"
            + (" (disabled)" if not dto.enabled else ""),
        )

    @channel_app.command("list")
    def channel_list(
        fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format"),
    ) -> None:
        result = _run(composition.list_channels.execute({}))
        if fmt == OutputFormat.JSON:
            console.print_json(data=[dto.model_dump(mode="json") for dto in result.items])
            return
        table = Table("id", "name", "kind", "enabled", "has_secret")
        for dto in result.items:
            table.add_row(
                str(dto.id),
                dto.name,
                dto.kind,
                str(dto.enabled),
                str(dto.has_secret),
            )
        console.print(table)

    @channel_app.command("rm")
    def channel_rm(channel_id: str = typer.Argument(...)) -> None:
        _run(composition.delete_channel.execute(UUID(channel_id)))
        console.print(f"removed channel id={channel_id}")

    @channel_app.command("enable")
    def channel_enable(channel_id: str = typer.Argument(...)) -> None:
        dto = _run(
            composition.update_channel.execute(
                {
                    "id": UUID(channel_id),
                    "input": UpdateChannelInput(enabled=True),
                },
            ),
        )
        console.print(f"enabled channel [bold]{dto.name}[/]")

    @channel_app.command("disable")
    def channel_disable(channel_id: str = typer.Argument(...)) -> None:
        dto = _run(
            composition.update_channel.execute(
                {
                    "id": UUID(channel_id),
                    "input": UpdateChannelInput(enabled=False),
                },
            ),
        )
        console.print(f"disabled channel [bold]{dto.name}[/]")

    @binding_app.command("add")
    def binding_add(
        channel: str = typer.Option(..., "--channel", help="Channel id"),
        scope: str = typer.Option(..., "--scope", help="global|domain|category|url"),
        scope_id: str | None = typer.Option(None, "--scope-id"),
        on_change: bool = typer.Option(True, "--on-change/--no-on-change"),
        on_error: bool = typer.Option(False, "--on-error/--no-on-error"),
        on_no_change: bool = typer.Option(False, "--on-no-change/--no-on-no-change"),
    ) -> None:
        scope_uuid = UUID(scope_id) if scope_id is not None else None
        dto = _run(
            composition.create_channel_binding.execute(
                CreateChannelBindingInput(
                    channel_id=UUID(channel),
                    scope=scope,
                    scope_id=scope_uuid,
                    on_change=on_change,
                    on_error=on_error,
                    on_no_change=on_no_change,
                ),
            ),
        )
        console.print(
            f"created binding id={dto.id} channel={dto.channel_id} scope={dto.scope}",
        )

    @binding_app.command("list")
    def binding_list(
        scope: str | None = typer.Option(None, "--scope"),
        scope_id: str | None = typer.Option(None, "--scope-id"),
        fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format"),
    ) -> None:
        params: dict[str, Any] = {}
        if scope is not None:
            params["scope"] = scope
        if scope_id is not None:
            params["scope_id"] = UUID(scope_id)
        result = _run(composition.list_channel_bindings.execute(params))
        if fmt == OutputFormat.JSON:
            console.print_json(data=[dto.model_dump(mode="json") for dto in result.items])
            return
        table = Table("id", "channel_id", "scope", "scope_id", "on_change", "on_error", "on_no_change")
        for dto in result.items:
            table.add_row(
                str(dto.id),
                str(dto.channel_id),
                dto.scope,
                str(dto.scope_id) if dto.scope_id else "",
                str(dto.on_change),
                str(dto.on_error),
                str(dto.on_no_change),
            )
        console.print(table)

    @binding_app.command("update")
    def binding_update(
        binding_id: str = typer.Argument(...),
        on_change: bool | None = typer.Option(None, "--on-change/--no-on-change"),
        on_error: bool | None = typer.Option(None, "--on-error/--no-on-error"),
        on_no_change: bool | None = typer.Option(None, "--on-no-change/--no-on-no-change"),
    ) -> None:
        dto = _run(
            composition.update_channel_binding.execute(
                {
                    "id": UUID(binding_id),
                    "input": UpdateChannelBindingInput(
                        on_change=on_change,
                        on_error=on_error,
                        on_no_change=on_no_change,
                    ),
                },
            ),
        )
        console.print(f"updated binding id={dto.id}")

    @binding_app.command("rm")
    def binding_rm(binding_id: str = typer.Argument(...)) -> None:
        _run(composition.delete_channel_binding.execute(UUID(binding_id)))
        console.print(f"removed binding id={binding_id}")

    @notify_app.command("test")
    def test_notify_cmd(channel: str = typer.Option(..., "--channel")) -> None:
        if composition.send_test_notification is None:
            console.print(
                "[red]test-notify unavailable: no notifier/renderer configured[/]",
            )
            raise typer.Exit(code=1)
        result = _run(
            composition.send_test_notification.execute(UUID(channel)),
        )
        if result.success:
            console.print(f"[green]delivered test to channel {result.channel_id}[/]")
            return
        console.print(f"[red]test-notify failed: {result.error}[/]")
        raise typer.Exit(code=1)

    @app.command("learn-zones")
    def learn_zones_cmd(
        domain: str = typer.Option(..., "--domain", help="Domain host to learn zones for."),
        dry_run: bool = typer.Option(True, "--dry-run/--no-dry-run"),
    ) -> None:
        if composition.learn_zones is None:
            console.print("[red]learn-zones unavailable: no learner configured[/]")
            raise typer.Exit(code=1)
        result = _run(
            composition.learn_zones.execute(
                {"domain": domain, "dry_run": dry_run, "observations": []},
            ),
        )
        console.print(f"[green]zones learned for {domain}[/]")
        console.print(f"  signal zones: {', '.join(result.signal_zones) or '(none)'}")
        console.print(f"  noise zones:  {', '.join(result.noise_zones) or '(none)'}")
        console.print(f"  observations used: {result.observations_used}")
        if result.zone_selectors:
            table = Table("zone", "selector", "weight", "noise")
            for z in result.zone_selectors:
                table.add_row(z["name"], z["css_selector"], str(z["weight"]), str(z["is_noise"]))
            console.print(table)

    @app.command("cluster-templates")
    def cluster_templates_cmd(
        domain: str = typer.Option(..., "--domain", help="Domain host to cluster."),
    ) -> None:
        if composition.cluster_templates is None:
            console.print("[red]cluster-templates unavailable: no clusterer configured[/]")
            raise typer.Exit(code=1)
        result = _run(
            composition.cluster_templates.execute(
                {"domain": domain, "skeletons": []},
            ),
        )
        console.print(f"[green]clustering complete for {domain}[/]")
        console.print(f"  urls clustered: {result.urls_clustered}")
        console.print(f"  clusters: {len(result.clusters)}")
        console.print(f"  drift profiles: {', '.join(result.drift_profiles) or '(none)'}")

    @app.command("eval")
    def eval_cmd(
        fmt: OutputFormat = typer.Option(OutputFormat.TABLE, "--format"),
    ) -> None:
        if composition.eval_pipeline is None:
            console.print("[red]eval unavailable: no eval pipeline configured[/]")
            raise typer.Exit(code=1)
        result = _run(
            composition.eval_pipeline.execute({"changes": [], "labels": []}),
        )
        if fmt == OutputFormat.JSON:
            console.print_json(data=result.model_dump(mode="json"))
            return
        console.print("[bold]Eval Pipeline Results[/]")
        console.print(f"  total changes:     {result.total_changes}")
        console.print(f"  true positives:    {result.true_positives}")
        console.print(f"  false positives:   {result.false_positives}")
        console.print(f"  true negatives:    {result.true_negatives}")
        console.print(f"  false negatives:   {result.false_negatives}")
        console.print(f"  precision:         {result.precision:.4f}")
        console.print(f"  recall:            {result.recall:.4f}")
        console.print(f"  escalation rate:   {result.escalation_rate:.4f}")
        console.print(f"  FP vs lexical:     {result.fps_vs_lexical_only:.4f}")

    @app.command("label")
    def label_cmd(
        change_id: str = typer.Option(..., "--change-id"),
        is_change: bool = typer.Option(True, "--is-change/--not-change"),
        is_meaningful: bool | None = typer.Option(None, "--meaningful/--not-meaningful"),
        change_type: str | None = typer.Option(None, "--type"),
        labeled_by: str = typer.Option("human", "--labeled-by"),
    ) -> None:
        if composition.label_changes is None:
            console.print("[red]label unavailable: no label repo configured[/]")
            raise typer.Exit(code=1)
        result = _run(
            composition.label_changes.execute(
                {
                    "labels": [
                        {
                            "change_id": change_id,
                            "is_change": is_change,
                            "is_meaningful": is_meaningful,
                            "change_type": change_type,
                            "labeled_by": labeled_by,
                        },
                    ],
                },
            ),
        )
        if result.errors:
            for err in result.errors:
                console.print(f"[red]{err}[/]")
            raise typer.Exit(code=1)
        console.print(f"[green]labeled {result.labeled}[/] change(s)")

    return app
