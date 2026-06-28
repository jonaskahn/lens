"""Broker adapters: in-memory broker and RabbitMQ skeleton.

The :class:`InMemoryBroker` is the canonical implementation: it
implements both :class:`TaskPublisherPort` and a synchronous consumer
loop for :class:`TaskSubscriberPort`, so the worker can be exercised
end-to-end without a real broker.

The :class:`RabbitTaskPublisher` skeleton uses aio-pika and the
RabbitMQ topology for the task exchange; it is imported lazily so
production deployments can opt in without forcing the dependency at
import time in tests.

The event side adds :class:`InMemoryEventPublisher`,
:class:`InMemoryEventConsumer`, and :class:`RabbitEventConsumer` for
the ``events`` exchange that the notifier subscribes to. The outbox
relay publishes via the publisher; the notifier subscribes via the
consumer.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from lens_application.pipeline import (
    CrawlTask,
    EventConsumerPort,
    EventPublisherPort,
    TaskPublisherPort,
    TaskSubscriberPort,
)

__all__ = [
    "InMemoryBroker",
    "InMemoryEventConsumer",
    "InMemoryEventPublisher",
    "InMemoryTaskPublisher",
    "InMemoryTaskSubscriber",
    "RabbitEventConsumer",
    "RabbitTaskPublisher",
]


@dataclass
class _Envelope:
    routing_key: str
    body: dict[str, Any]
    message_id: UUID
    occurred_at: Any


class InMemoryBroker:
    """A tiny in-memory broker with one queue per routing key.

    The broker implements publish / consume semantics close enough to
    RabbitMQ for the worker tests. Multiple consumers attached to the
    same queue use a single shared :class:`asyncio.Queue`.
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[_Envelope]] = {}

    def _queue(self, routing_key: str) -> asyncio.Queue[_Envelope]:
        if routing_key not in self._queues:
            self._queues[routing_key] = asyncio.Queue()
        return self._queues[routing_key]

    def attach_consumer(self, routing_key: str) -> asyncio.Queue[_Envelope]:
        """Return the queue for ``routing_key``.

        There is exactly one queue per routing key in the in-memory broker;
        multiple subscribers share the same messages (competing-consumer
        semantics is the responsibility of the worker pool, not the broker).
        """
        return self._queue(routing_key)

    async def publish(self, routing_key: str, body: dict[str, Any]) -> None:
        env = _Envelope(
            routing_key=routing_key,
            body=body,
            message_id=UUID(int=0),
            occurred_at=datetime.now(UTC),
        )
        await self._queue(routing_key).put(env)


class InMemoryTaskPublisher(TaskPublisherPort):
    """Publish :class:`CrawlTask` messages to an :class:`InMemoryBroker`."""

    def __init__(self, broker: InMemoryBroker, *, routing_key: str = "crawl.task") -> None:
        self._broker = broker
        self._routing_key = routing_key

    async def publish_crawl_task(self, task: CrawlTask) -> None:
        body = {
            "message_id": str(UUID(int=0)),
            "type": "CrawlTask",
            "occurred_at": task.scheduled_slot.isoformat(),
            "data": {
                "url_id": str(task.url_id),
                "task_id": task.task_id,
                "scheduled_slot": task.scheduled_slot.isoformat(),
                "reason": task.reason,
            },
        }
        await self._broker.publish(self._routing_key, body)


class InMemoryTaskSubscriber(TaskSubscriberPort):
    """Consume :class:`CrawlTask` messages from an :class:`InMemoryBroker`."""

    def __init__(
        self,
        broker: InMemoryBroker,
        *,
        routing_key: str = "crawl.task",
        prefetch: int = 4,
    ) -> None:
        self._broker = broker
        self._routing_key = routing_key
        self._prefetch = prefetch
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    async def start(
        self,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        prefetch: int = 1,
    ) -> None:
        queue = self._broker.attach_consumer(self._routing_key)
        self._stop.clear()

        async def _loop() -> None:
            while not self._stop.is_set():
                try:
                    env = await asyncio.wait_for(queue.get(), timeout=0.5)
                except TimeoutError:
                    continue
                with contextlib.suppress(Exception):
                    await handler(env.body)

        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task


class RabbitTaskPublisher(TaskPublisherPort):
    """A RabbitMQ-backed :class:`TaskPublisherPort` skeleton.

    Wire aio-pika at composition time. Publishing uses the durable
    ``crawl`` direct exchange with routing key ``crawl.task`` and a
    quorum queue bound to it.
    """

    def __init__(self, url: str, *, exchange: str = "crawl", routing_key: str = "crawl.task") -> None:
        self._url = url
        self._exchange_name = exchange
        self._routing_key = routing_key
        self._connection: Any = None
        self._channel: Any = None
        self._exchange: Any = None

    async def connect(self) -> None:
        try:
            import aio_pika
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("aio-pika is required for RabbitTaskPublisher") from exc
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel(publisher_confirms=True)
        self._exchange = await self._channel.declare_exchange(
            self._exchange_name,
            type=aio_pika.ExchangeType.DIRECT,
            durable=True,
        )
        queue = await self._channel.declare_queue(
            "crawl.tasks",
            durable=True,
            arguments={"x-queue-type": "quorum"},
        )
        await queue.bind(self._exchange, routing_key=self._routing_key)

    async def publish_crawl_task(self, task: CrawlTask) -> None:
        if self._exchange is None:
            await self.connect()
        import aio_pika

        body = json.dumps(
            {
                "message_id": str(UUID(int=0)),
                "type": "CrawlTask",
                "occurred_at": task.scheduled_slot.isoformat(),
                "data": {
                    "url_id": str(task.url_id),
                    "task_id": task.task_id,
                    "scheduled_slot": task.scheduled_slot.isoformat(),
                    "reason": task.reason,
                },
            },
        ).encode("utf-8")
        assert self._exchange is not None, "exchange not connected"
        await self._exchange.publish(
            aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=self._routing_key,
        )

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()


# ---------------------------------------------------------------------------
# Event publisher / consumer (events exchange, change.events queue)
# ---------------------------------------------------------------------------


class InMemoryEventPublisher(EventPublisherPort):
    """An in-memory :class:`EventPublisherPort` for the notifier."""

    def __init__(self, broker: InMemoryBroker) -> None:
        self._broker = broker

    async def publish(
        self,
        *,
        exchange: str,
        routing_key: str,
        body: dict[str, Any],
    ) -> None:
        # In-memory broker collapses (exchange, routing_key) into one queue
        # keyed by the routing key (the exchange is implicit in tests).
        _ = exchange
        await self._broker.publish(routing_key, body)


class InMemoryEventConsumer(EventConsumerPort):
    """An in-memory :class:`EventConsumerPort` for tests + dev runs."""

    def __init__(
        self,
        broker: InMemoryBroker,
        *,
        routing_keys: tuple[str, ...] = ("url.changed", "url.failed", "url.stale"),
        prefetch: int = 8,
    ) -> None:
        self._broker = broker
        self._routing_keys = routing_keys
        self._prefetch = prefetch
        self._tasks: list[asyncio.Task[None]] = []
        self._stop = asyncio.Event()

    async def start(
        self,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        prefetch: int = 1,
    ) -> None:
        _ = prefetch
        self._stop.clear()

        async def _consume_one(routing_key: str) -> None:
            queue = self._broker.attach_consumer(routing_key)
            while not self._stop.is_set():
                try:
                    env = await asyncio.wait_for(queue.get(), timeout=0.5)
                except TimeoutError:
                    continue
                with contextlib.suppress(Exception):
                    await handler(env.body)

        for routing_key in self._routing_keys:
            self._tasks.append(asyncio.create_task(_consume_one(routing_key)))

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            await task
        self._tasks.clear()


class RabbitEventConsumer(EventConsumerPort):
    """A RabbitMQ-backed :class:`EventConsumerPort` skeleton.

    Subscribes to the ``change.events`` topic queue (bound to the
    ``events`` topic exchange with keys ``url.*``, ``site.drift``,
    ``change.enriched``) and dispatches a handler per message. The
    consumer uses manual ack so the application layer can decide on
    retry/DLQ behaviour.
    """

    def __init__(
        self,
        url: str,
        *,
        exchange: str = "events",
        routing_keys: tuple[str, ...] = (
            "url.changed",
            "url.failed",
            "url.stale",
            "site.drift",
            "change.enriched",
        ),
        queue: str = "change.events",
        prefetch: int = 8,
    ) -> None:
        self._url = url
        self._exchange_name = exchange
        self._routing_keys = routing_keys
        self._queue_name = queue
        self._prefetch = prefetch
        self._connection: Any = None
        self._channel: Any = None
        self._queue: Any = None
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def connect(self) -> None:
        try:
            import aio_pika
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("aio-pika is required for RabbitEventConsumer") from exc
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()

    async def _ensure_qos(self, prefetch: int) -> None:
        if self._channel is None:
            await self.connect()
        assert self._channel is not None
        await self._channel.set_qos(prefetch_count=prefetch)

    async def _ensure_topology(self) -> None:
        assert self._channel is not None
        try:
            import aio_pika
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("aio-pika is required for RabbitEventConsumer") from exc
        exchange = await self._channel.declare_exchange(
            self._exchange_name,
            type=aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        self._queue = await self._channel.declare_queue(
            self._queue_name,
            durable=True,
            arguments={"x-queue-type": "quorum"},
        )
        for routing_key in self._routing_keys:
            await self._queue.bind(exchange, routing_key=routing_key)

    async def start(
        self,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        prefetch: int = 1,
    ) -> None:
        if self._channel is None:
            await self.connect()
        effective_prefetch = prefetch if prefetch > 1 else self._prefetch
        await self._ensure_qos(effective_prefetch)
        await self._ensure_topology()
        self._stop.clear()

        async def _loop() -> None:
            assert self._queue is not None
            async with self._queue.iterator() as it:
                async for message in it:
                    if self._stop.is_set():
                        break
                    async with message.process(requeue=False):
                        try:
                            body = json.loads(message.body.decode("utf-8"))
                        except Exception:
                            continue
                        with contextlib.suppress(Exception):
                            await handler(body)

        self._task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
        if self._connection is not None:
            await self._connection.close()
