"""CLI entrypoint.

The CLI uses Typer; the default :func:`run` builds a Postgres-backed
composition root when a real database is available. For local development
and tests, build a Typer app via :func:`build_app` and pass a
``CliComposition`` wired to the in-memory fakes.
"""

from __future__ import annotations

from collections.abc import Callable

from lens_application.ports import UnitOfWork
from lens_cli.commands import build_app
from lens_cli.composition import build_cli_composition
from lens_cli.settings import CliSettings
from lens_common.config import load_settings
from lens_common.logging import configure_logging
from lens_infrastructure.notifier import AppriseNotifier
from lens_infrastructure.secret_provider import ChannelSecretProvider
from lens_infrastructure.template_renderer import JinjaTemplateRenderer

__all__ = ["build_cli_composition", "run"]


def run(uow_factory: Callable[[], UnitOfWork] | None = None) -> None:
    """Entry point for the ``lens`` console script.

    When ``uow_factory`` is omitted, constructs a Postgres-backed factory
    from ``LENS_DATABASE_URL``. Tests should construct a
    :class:`CliComposition` and use :func:`build_app` directly.
    """
    settings = load_settings(CliSettings)
    configure_logging(level=settings.log_level, fmt=settings.log_format, force=True)
    if uow_factory is None:
        if settings.database_url is None:

            def _default() -> UnitOfWork:
                raise RuntimeError(
                    "CLI needs a UoW factory; set LENS_DATABASE_URL or pass a factory.",
                )

            uow_factory = _default
        else:
            from sqlalchemy.engine import Engine

            from lens_infrastructure.db.base import create_engine_for_url
            from lens_infrastructure.db.unit_of_work import sqlalchemy_uow_factory

            engine: Engine = create_engine_for_url(settings.database_url)
            uow_factory = sqlalchemy_uow_factory(engine)

    composition = build_cli_composition(
        uow_factory,
        renderer=JinjaTemplateRenderer(),
        notifier=AppriseNotifier(),
        secrets=ChannelSecretProvider(),
    )
    app = build_app(composition)
    app()
