"""GracefulShutdown lifecycle tests."""

from __future__ import annotations

import asyncio

from lens_common.lifecycle import GracefulShutdown


class TestGracefulShutdown:
    async def test_register_hook_appends(self) -> None:
        gs = GracefulShutdown()
        called: list[str] = []

        async def hook() -> None:
            called.append("a")

        gs.register(hook)
        assert len(gs._hooks) == 1

    async def test_wait_returns_after_shutdown_event_set(self) -> None:
        gs = GracefulShutdown()
        gs._shutdown_event.set()
        await asyncio.wait_for(gs.wait(), timeout=1)

    async def test_should_exit_false_initially(self) -> None:
        gs = GracefulShutdown()
        assert gs.should_exit is False

    async def test_should_exit_true_after_trigger(self) -> None:
        gs = GracefulShutdown()
        gs._trigger()
        assert gs.should_exit is True

    async def test_shutdown_event_property(self) -> None:
        gs = GracefulShutdown()
        assert isinstance(gs.shutdown_event, asyncio.Event)
        assert not gs.shutdown_event.is_set()
        gs._trigger()
        assert gs.shutdown_event.is_set()

    async def test_shutdown_runs_all_hooks(self) -> None:
        gs = GracefulShutdown()
        results: list[str] = []

        async def hook_a() -> None:
            results.append("a")

        async def hook_b() -> None:
            results.append("b")

        gs.register(hook_a)
        gs.register(hook_b)
        await gs.shutdown()
        assert results == ["a", "b"]

    async def test_shutdown_handles_failing_hook(self) -> None:
        gs = GracefulShutdown()
        results: list[str] = []

        async def hook_ok() -> None:
            results.append("ok")

        async def hook_fail() -> None:
            raise RuntimeError("failed")

        gs.register(hook_ok)
        gs.register(hook_fail)
        await gs.shutdown()
        assert results == ["ok"]

    async def test_shutdown_event_default_not_set(self) -> None:
        gs = GracefulShutdown()
        assert gs.should_exit is False
        assert not gs.shutdown_event.is_set()

    async def test_wait_blocks_until_trigger(self) -> None:
        gs = GracefulShutdown()

        async def trigger_later() -> None:
            await asyncio.sleep(0.01)
            gs._trigger()

        task = asyncio.create_task(trigger_later())
        await asyncio.wait_for(gs.wait(), timeout=1)
        await task
