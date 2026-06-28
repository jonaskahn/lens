"""Tests for the in-process lock and broker adapters."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from lens_application.pipeline import CrawlTask
from lens_infrastructure.broker import (
    InMemoryBroker,
    InMemoryTaskPublisher,
    InMemoryTaskSubscriber,
)
from lens_infrastructure.locks import InMemoryLockAdapter


@pytest.mark.asyncio
async def test_given_unheld_lock_when_acquire_then_token_returned() -> None:
    lock = InMemoryLockAdapter()
    token = await lock.acquire("k1", ttl_seconds=10, token="t1")
    assert token == "t1"


@pytest.mark.asyncio
async def test_given_held_lock_when_acquire_then_empty() -> None:
    lock = InMemoryLockAdapter()
    await lock.acquire("k1", ttl_seconds=10, token="t1")
    token = await lock.acquire("k1", ttl_seconds=10, token="t2")
    assert token == ""


@pytest.mark.asyncio
async def test_given_lock_held_by_self_when_release_then_cleared() -> None:
    lock = InMemoryLockAdapter()
    await lock.acquire("k1", ttl_seconds=10, token="t1")
    await lock.release("k1", "t1")
    token = await lock.acquire("k1", ttl_seconds=10, token="t2")
    assert token == "t2"


@pytest.mark.asyncio
async def test_given_in_memory_broker_when_publish_then_consumer_receives() -> None:
    broker = InMemoryBroker()
    publisher = InMemoryTaskPublisher(broker, routing_key="crawl.task")
    subscriber = InMemoryTaskSubscriber(broker, routing_key="crawl.task")

    received: list[dict] = []

    async def handler(body: dict) -> None:
        received.append(body)

    await subscriber.start(handler, prefetch=1)
    url_id = uuid4()
    await publisher.publish_crawl_task(
        CrawlTask(
            url_id=url_id,
            task_id="t-1",
            scheduled_slot=datetime.now(UTC),
            reason="scheduled",
        ),
    )
    await asyncio.sleep(0.2)
    await subscriber.stop()
    assert len(received) == 1
    assert received[0]["data"]["url_id"] == str(url_id)
    assert received[0]["data"]["task_id"] == "t-1"
