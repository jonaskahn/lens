"""Production composition: wire the SQLAlchemy UoW, DB key lookup, and Redis.

The :func:`build_production_composition` entrypoint is the only place
that touches the real infrastructure (Postgres, Redis, the message
broker). It returns a fully-wired :class:`Composition` plus the
auxiliary collaborators the :func:`create_app` factory needs
(``api_key_lookup`` and the ``RateLimiter``).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from lens_api.composition import Composition, build_composition
from lens_api.rate_limit import RateLimiter
from lens_application.pipeline import BlobStoragePort
from lens_application.ports import UnitOfWork
from lens_application.use_cases.scaling import RetentionDeps
from lens_common.health import ComponentStatus, HealthCheck
from lens_infrastructure.db.unit_of_work import (
    sqlalchemy_uow_factory,
)
from lens_infrastructure.storage import (
    AsyncLocalFileBlobStorage,
    LocalFileBlobStorage,
)

__all__ = [
    "RedisRateLimiter",
    "build_production_composition",
    "db_api_key_lookup",
    "db_check",
    "register_dependency_checks",
    "sqlalchemy_blob_storage",
]


def db_api_key_lookup(engine: Engine) -> Callable[[str], dict[str, Any] | None]:
    """Return an ``api_key_lookup`` backed by the ``api_keys`` table.

    The returned callable takes a SHA-256 hex digest of the bearer
    token and returns a dict matching the contract
    :func:`lens_api.auth.resolve_api_key` expects, or ``None`` when the
    key is unknown.
    """

    def _lookup(key_hash: str) -> dict[str, Any] | None:
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT id, name, scopes, enabled FROM api_keys WHERE key_hash = :h"),
                {"h": key_hash},
            ).first()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "name": row.name,
            "scopes": list(row.scopes or []),
            "enabled": bool(row.enabled),
        }

    return _lookup


def sqlalchemy_blob_storage(root: str) -> BlobStoragePort:
    """Return a :class:`BlobStoragePort` backed by local gzip-compressed files.

    Wraps the *sync* :class:`LocalFileBlobStorage` in an
    :class:`AsyncLocalFileBlobStorage` so it satisfies the async
    application :class:`BlobStoragePort` protocol.
    """
    return AsyncLocalFileBlobStorage(inner=LocalFileBlobStorage(root=Path(root)))


async def db_check(engine: Engine, *, timeout: float = 2.0) -> ComponentStatus:
    """Probe the database for :class:`HealthCheck`.

    Runs ``SELECT 1`` under :func:`asyncio.wait_for` so a wedged
    backend cannot block the probe beyond ``timeout`` seconds (per
    ``COMMON-009``).
    """

    def _probe() -> None:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(asyncio.to_thread(_probe), timeout=timeout)
    except Exception as exc:
        return ComponentStatus(healthy=False, details={"error": str(exc)})
    return ComponentStatus(healthy=True, details={"backend": engine.dialect.name})


def register_dependency_checks(
    health: HealthCheck,
    *,
    engine: Engine | None = None,
    redis_client: Any = None,
    broker_ping: Callable[[], Any] | None = None,
    timeout: float = 2.0,
) -> None:
    """Register readiness probes for the documented dependencies.

    The probes are non-blocking: each one runs under
    :func:`asyncio.wait_for` and reports the failure reason in
    ``details`` so operators can grep for it in the JSON response.
    """

    async def _check_db() -> ComponentStatus:
        if engine is None:
            return ComponentStatus(healthy=True, details={"skipped": True})
        return await db_check(engine, timeout=timeout)

    async def _check_redis() -> ComponentStatus:
        if redis_client is None:
            return ComponentStatus(healthy=True, details={"skipped": True})

        async def _ping() -> None:
            await redis_client.ping()

        try:
            await asyncio.wait_for(_ping(), timeout=timeout)
        except Exception as exc:
            return ComponentStatus(healthy=False, details={"error": str(exc)})
        return ComponentStatus(healthy=True)

    async def _check_broker() -> ComponentStatus:
        if broker_ping is None:
            return ComponentStatus(healthy=True, details={"skipped": True})
        try:
            await asyncio.wait_for(broker_ping(), timeout=timeout)
        except Exception as exc:
            return ComponentStatus(healthy=False, details={"error": str(exc)})
        return ComponentStatus(healthy=True)

    health.add_check("database", _check_db)
    health.add_ready_check("database", _check_db)
    if redis_client is not None:
        health.add_ready_check("redis", _check_redis)
    if broker_ping is not None:
        health.add_ready_check("broker", _check_broker)


class RedisRateLimiter(RateLimiter):
    """Redis-backed sliding-window rate limiter.

    Uses a single ``ZADD`` + ``ZREMRANGEBYSCORE`` Lua script to keep
    the window maintenance atomic; the limiter is safe across
    multiple API replicas.
    """

    _SLIDING_WINDOW_LUA = """
    local key = KEYS[1]
    local now_ms = tonumber(ARGV[1])
    local window_ms = tonumber(ARGV[2])
    local max_requests = tonumber(ARGV[3])
    local cutoff = now_ms - window_ms
    redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
    local current = redis.call('ZCARD', key)
    if current >= max_requests then
        return 0
    end
    redis.call('ZADD', key, now_ms, now_ms .. ':' .. tostring(math.random()))
    redis.call('PEXPIRE', key, window_ms)
    return 1
    """

    def __init__(self, redis: Any) -> None:
        self._redis = redis

    async def is_allowed(self, key: str, *, max_requests: int, window_seconds: int) -> bool:
        full_key = f"lens:rate:{key}"
        now_ms = int(time.time() * 1000)
        window_ms = window_seconds * 1000
        try:
            allowed = await self._redis.eval(
                self._SLIDING_WINDOW_LUA,
                1,
                full_key,
                str(now_ms),
                str(window_ms),
                str(max_requests),
            )
        except Exception:
            return False
        return bool(allowed)

    async def reset(self, key: str) -> None:
        with contextlib.suppress(Exception):
            await self._redis.delete(f"lens:rate:{key}")


def _build_retention_deps(local: LocalFileBlobStorage, root: Path) -> RetentionDeps:
    """Wrap a :class:`LocalFileBlobStorage` as :class:`RetentionDeps`."""

    def _delete(key: str) -> None:
        local.delete(key)

    def _list_keys() -> list[str]:
        return [str(p.relative_to(root)) for p in root.rglob("*.gz")]

    return RetentionDeps(blob_delete=_delete, blob_list_keys=_list_keys)


def build_production_composition(
    engine: Engine,
    *,
    blob_root: str | None = None,
    max_snapshots: int = 25,
    api_key_lookup: Callable[[str], dict[str, Any] | None] | None = None,
    task_publisher: Any = None,
    dlq: Any = None,
    settings_repo: Any = None,
    config_broadcast: Any = None,
    classification_repo: Any = None,
    health_check: HealthCheck | None = None,
) -> tuple[Composition, Callable[[str], dict[str, Any] | None]]:
    """Wire a real :class:`Composition` and the ``api_key_lookup`` callable.

    The returned tuple is what :func:`lens_api.main.create_app` expects:
    pass the composition to the factory and the lookup to
    ``api_key_lookup=...``.
    """
    uow_factory: Callable[[], UnitOfWork] = sqlalchemy_uow_factory(engine)
    blob_storage: BlobStoragePort | None = None
    retention_deps: RetentionDeps | None = None
    if blob_root is not None:
        root = Path(blob_root)
        local = LocalFileBlobStorage(root=root)
        blob_storage = AsyncLocalFileBlobStorage(inner=local)
        retention_deps = _build_retention_deps(local, root)
    composition = build_composition(
        uow_factory,
        task_publisher=task_publisher,
        dlq=dlq,
        settings_repo=settings_repo,
        config_broadcast=config_broadcast,
        classification_repo=classification_repo,
        blob_storage=blob_storage,
        retention_deps=retention_deps,
        max_snapshots=max_snapshots,
    )
    if health_check is not None:
        register_dependency_checks(health_check, engine=engine)
    lookup = api_key_lookup or db_api_key_lookup(engine)
    return composition, lookup
