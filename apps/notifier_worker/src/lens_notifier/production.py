"""Production composition for the notifier worker.

Builds the real Postgres-backed :class:`UnitOfWork` factory, the
:class:`RabbitEventConsumer`, an :class:`AppriseNotifier`, the
:class:`JinjaTemplateRenderer`, a Redis-backed throttle / idempotency /
DLQ, a local-filesystem blob store, and the outbox publisher. The
resulting :class:`NotifierComposition` is consumed by
:func:`lens_notifier.main.run`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine

from lens_application.pipeline import ChannelSecretProvider, EventConsumerPort, EventPublisherPort
from lens_application.ports import UnitOfWork
from lens_infrastructure.broker import RabbitEventConsumer
from lens_infrastructure.db.unit_of_work import sqlalchemy_uow_factory
from lens_infrastructure.dead_letter import RedisDeadLetterStore
from lens_infrastructure.idempotency import RedisIdempotencyStore
from lens_infrastructure.notifier import AppriseNotifier
from lens_infrastructure.secret_provider import ChannelSecretProvider as _DefaultChannelSecretProvider
from lens_infrastructure.storage import (
    AsyncLocalFileBlobStorage,
    LocalFileBlobStorage,
)
from lens_infrastructure.template_renderer import JinjaTemplateRenderer
from lens_infrastructure.throttle import RedisThrottle
from lens_notifier.main import NotifierComposition, build_notifier_worker
from lens_notifier.settings import NotifierSettings

__all__ = ["build_production_composition", "notifier_redis_client"]


def notifier_redis_client(url: str) -> Any:
    """Build an async Redis client for the notifier's hot-path collaborators.

    Imported lazily so the notifier does not require ``redis.asyncio`` at
    test time; the dependency is only resolved when the production
    composition is constructed.
    """
    try:
        import redis.asyncio as aioredis
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "redis.asyncio is required for the production notifier composition",
        ) from exc
    return aioredis.from_url(url, decode_responses=True)


def build_production_composition(
    engine: Engine,
    *,
    settings: NotifierSettings,
    publisher: EventPublisherPort,
    redis_url: str | None = None,
    blob_root: str | None = None,
    consumer: EventConsumerPort | None = None,
    secrets: ChannelSecretProvider | None = None,
    uow_factory: Callable[[], UnitOfWork] | None = None,
) -> NotifierComposition:
    """Wire a real :class:`NotifierComposition` for production use.

    Args:
        engine: SQLAlchemy engine used to build the Postgres-backed
            ``uow_factory``. A factory is constructed with
            :func:`sqlalchemy_uow_factory` when one is not supplied.
        settings: Notifier configuration (prefetch, batch sizes, retry
            base, max attempts, per-channel rate).
        publisher: Pre-built :class:`EventPublisherPort` used by both
            the outbox relay and the retry-republish path. Required.
        redis_url: Optional Redis URL. When provided, the composition
            is built with real Redis-backed throttle / idempotency /
            DLQ stores. When ``None``, the composition is built
            without them (so the relay / outbox-republish can still
            run).
        blob_root: Optional filesystem root for the local blob backend.
            When ``None``, the composition is built without a blob
            adapter (template rendering then skips the diff snippet).
        consumer: Optional pre-built :class:`EventConsumerPort` (e.g.
            a test double). When omitted, a :class:`RabbitEventConsumer`
            bound to ``settings.rabbitmq_url`` is constructed.
        secrets: Optional :class:`ChannelSecretProvider`; the default
            :class:`ChannelSecretProvider` reads the (decrypted) URL
            from the :class:`Channel` entity.
        uow_factory: Optional pre-built UoW factory. When omitted, one
            is built from ``engine`` via
            :func:`sqlalchemy_uow_factory`.

    Returns:
        A fully-wired :class:`NotifierComposition` ready for
        :func:`lens_notifier.main.run`.
    """
    factory = uow_factory or sqlalchemy_uow_factory(engine)
    blob_adapter: Any = None
    if blob_root is not None:
        local = LocalFileBlobStorage(root=Path(blob_root))
        blob_adapter = AsyncLocalFileBlobStorage(inner=local)
    notifier_impl = AppriseNotifier()
    renderer_impl = JinjaTemplateRenderer()
    secret_provider = secrets or _DefaultChannelSecretProvider()
    consumer_impl = consumer
    if consumer_impl is None and settings.rabbitmq_url is not None:
        consumer_impl = RabbitEventConsumer(
            settings.rabbitmq_url,
            prefetch=settings.notifier_prefetch,
        )
    throttle_impl: Any = None
    idempotency_impl: Any = None
    dlq_impl: Any = None
    if redis_url is not None:
        redis_client = notifier_redis_client(redis_url)
        throttle_impl = RedisThrottle(
            redis_client,
            max_rate=settings.per_channel_max_rate,
        )
        idempotency_impl = RedisIdempotencyStore(redis_client)
        dlq_impl = RedisDeadLetterStore(redis_client)
    return build_notifier_worker(
        settings=settings,
        uow_factory=factory,
        consumer=consumer_impl or _NoopEventConsumer(),
        notifier=notifier_impl,
        renderer=renderer_impl,
        blob=blob_adapter or _NoopBlobStorage(),
        outbox_publisher=publisher,
        throttle=throttle_impl,
        idempotency=idempotency_impl,
        dlq=dlq_impl,
        secret_provider=secret_provider,
    )


class _NoopBlobStorage:
    """A blob storage stub used when ``blob_root`` is not configured.

    The use case treats blob reads as best-effort; a missing blob is
    logged and the diff snippet is left empty. This stand-in keeps the
    application protocol satisfied without requiring a filesystem root.
    """

    async def put(self, key: str, data: bytes) -> str:
        return key

    async def get(self, key: str) -> bytes:
        return b""

    async def delete(self, key: str) -> None:
        return None


class _NoopEventConsumer:
    """A consumer stub used when no broker URL is configured.

    The composition's :meth:`start` and :meth:`stop` simply block on
    the shutdown event so the worker can still be exercised in dev
    without a live RabbitMQ instance.
    """

    async def start(
        self,
        handler: Any,
        *,
        prefetch: int = 1,
    ) -> None:
        return None

    async def stop(self) -> None:
        return None
