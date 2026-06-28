"""Tests for the outbox relay loop."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from tests._fakes import InMemoryUnitOfWork, reset_in_memory_store

from lens_infrastructure.outbox_relay import OutboxRelay, OutboxRelaySettings


@dataclass
class _CapturingPublisher:
    published: list[dict[str, Any]] = field(default_factory=list)

    async def publish(
        self,
        *,
        exchange: str,
        routing_key: str,
        body: dict[str, Any],
    ) -> None:
        self.published.append(
            {"exchange": exchange, "routing_key": routing_key, "body": body},
        )


async def _seed_outbox_rows(store: Any, count: int) -> list[UUID]:
    uow = InMemoryUnitOfWork(store=store)
    ids: list[UUID] = []
    for _ in range(count):
        row_id = uow.new_id()
        await uow.outbox.add(
            id=row_id,
            aggregate_type="url",
            aggregate_id=uuid4(),
            event_type="UrlChangeDetected",
            event_id=uuid4(),
            payload={"url_id": str(uuid4())},
            created_at=uow.now(),
        )
        ids.append(row_id)
    await uow.commit()
    return ids


def _uow_factory(store: Any) -> callable:  # type: ignore[type-arg]
    def _factory() -> InMemoryUnitOfWork:
        return InMemoryUnitOfWork(store=store)

    return _factory


async def test_given_pending_outbox_rows_when_relay_runs_then_published() -> None:
    store = reset_in_memory_store()
    await _seed_outbox_rows(store, 3)
    publisher = _CapturingPublisher()
    relay = OutboxRelay(
        _uow_factory(store),
        publisher,
        OutboxRelaySettings(tick_seconds=0.01, batch_size=10),
    )

    task = asyncio.create_task(relay.run())
    await asyncio.sleep(0.1)
    relay.request_stop()
    await task

    assert len(publisher.published) == 3
    uow = InMemoryUnitOfWork(store=store)
    assert await uow.outbox.list_unsent(limit=10) == []


async def test_given_no_outbox_rows_when_relay_runs_then_idle() -> None:
    store = reset_in_memory_store()
    publisher = _CapturingPublisher()
    relay = OutboxRelay(
        _uow_factory(store),
        publisher,
        OutboxRelaySettings(tick_seconds=0.01, batch_size=10),
    )

    task = asyncio.create_task(relay.run())
    await asyncio.sleep(0.05)
    relay.request_stop()
    await task

    assert publisher.published == []
