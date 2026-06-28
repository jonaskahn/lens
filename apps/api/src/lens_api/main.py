"""FastAPI app factory + entrypoint."""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Callable
from typing import Any

import uvicorn
from dotenv import dotenv_values, load_dotenv
from fastapi import FastAPI

from lens_api.composition import build_composition
from lens_api.correlation import CorrelationIdMiddleware
from lens_api.errors import register_exception_handlers
from lens_api.rate_limit import InMemoryRateLimiter, RateLimiter, RateLimitMiddleware
from lens_api.routers import build_routers
from lens_api.settings import ApiSettings
from lens_application.ports import UnitOfWork
from lens_common.config import load_settings
from lens_common.logging import configure_logging

__all__ = ["create_app", "run"]


_logger = logging.getLogger("lens_api")


def create_app(
    settings: ApiSettings | None = None,
    *,
    uow_factory: Callable[[], UnitOfWork] | None = None,
    api_key_lookup: Callable[[str], dict[str, Any] | None] | None = None,
    rate_limiter: RateLimiter | None = None,
) -> FastAPI:
    """Build the FastAPI app with composition root, routers, and handlers.

    Tests pass an in-memory ``uow_factory`` and an ``api_key_lookup`` stub.
    Production wires a real Postgres-backed factory and a DB lookup.
    """
    if settings is None:
        settings = load_settings(ApiSettings)

    configure_logging(level=settings.log_level, fmt=settings.log_format, force=True)
    app = FastAPI(
        title="lens API",
        version="0.1.0",
        openapi_url="/openapi.json",
        docs_url="/docs",
    )

    limiter = rate_limiter or InMemoryRateLimiter()
    app.add_middleware(
        RateLimitMiddleware,
        limiter=limiter,
        max_requests=settings.api_rate_limit,
        window_seconds=settings.api_rate_window,
    )
    app.add_middleware(CorrelationIdMiddleware)

    if uow_factory is None:

        def _default() -> UnitOfWork:
            raise RuntimeError(
                "no uow_factory configured; pass one to create_app() or "
                "wire a Postgres-backed factory in the composition root",
            )

        uow_factory = _default

    app.state.composition = build_composition(uow_factory)
    app.state.api_key_lookup = api_key_lookup or (lambda _h: None)
    app.state.settings = settings

    register_exception_handlers(app)
    for router in build_routers():
        app.include_router(router, prefix="/api/v1")
    return app


def _parse_bootstrap_entries(raw: str) -> list[tuple[str, str, list[str]]]:
    """Parse ``API_KEYS_BOOTSTRAP`` into ``(key_id, plaintext, scopes)`` tuples.

    Entries are semicolon-separated; each entry has the form ``id:key:scope1,scope2``.
    A single entry without semicolons (legacy comma-only format) is also accepted.
    """
    entries = []
    # Support both ";" (multi-entry) and the single-entry legacy format.
    separators = raw.split(";") if ";" in raw else [raw]
    for entry in separators:
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":", 2)
        if len(parts) != 3:
            _logger.warning("API_KEYS_BOOTSTRAP entry %r has wrong format, expected id:key:scopes", entry)
            continue
        key_id, plaintext, scopes_raw = parts
        entries.append((key_id.strip(), plaintext.strip(), [s.strip() for s in scopes_raw.split(",") if s.strip()]))
    return entries


def _build_bootstrap_lookup(raw: str) -> Callable[[str], dict[str, Any] | None]:
    """Build an in-memory ``api_key_lookup`` from ``API_KEYS_BOOTSTRAP``."""
    store: dict[str, dict[str, Any]] = {}
    for key_id, plaintext, scopes in _parse_bootstrap_entries(raw):
        key_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        store[key_hash] = {"id": key_id, "name": key_id, "scopes": scopes, "enabled": True}
        _logger.info("bootstrap api key loaded — id=%s scopes=%s", key_id, scopes)

    def _lookup(key_hash: str) -> dict[str, Any] | None:
        return store.get(key_hash)

    return _lookup


def _log_bootstrap_keys() -> None:
    """Log any API_KEYS_BOOTSTRAP entries at startup so devs know what key to use."""
    raw = (dotenv_values().get("API_KEYS_BOOTSTRAP") or "").strip()
    if not raw:
        return
    for key_id, plaintext, scopes in _parse_bootstrap_entries(raw):
        _logger.info("bootstrap api key — id=%s scopes=%s key=%s", key_id, scopes, plaintext)


def run() -> None:
    """Module entrypoint: load settings and start uvicorn."""
    load_dotenv()
    settings = load_settings(ApiSettings)
    configure_logging(level=settings.log_level, fmt=settings.log_format, force=True)

    api_key_lookup: Callable[[str], dict[str, Any] | None] | None = None
    uow_factory: Callable[[], UnitOfWork] | None = None

    bootstrap_raw = (os.environ.get("API_KEYS_BOOTSTRAP") or "").strip()
    if bootstrap_raw:
        api_key_lookup = _build_bootstrap_lookup(bootstrap_raw)

    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    if database_url:
        try:
            from lens_infrastructure.db.base import create_engine_for_url
            from lens_infrastructure.db.unit_of_work import sqlalchemy_uow_factory

            sync_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
            engine = create_engine_for_url(sync_url)
            uow_factory = sqlalchemy_uow_factory(engine)

            if api_key_lookup is None:
                from lens_api.production import db_api_key_lookup

                api_key_lookup = db_api_key_lookup(engine)
        except Exception:
            _logger.exception("failed to connect to database — running without DB")

    app = create_app(settings, uow_factory=uow_factory, api_key_lookup=api_key_lookup)
    _log_bootstrap_keys()
    _logger.info("starting lens_api on 0.0.0.0:8000 (role=%s)", settings.app_role)
    uvicorn.run(app, host="0.0.0.0", port=8000)
