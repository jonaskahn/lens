from __future__ import annotations

import asyncio
import signal
from collections.abc import Awaitable, Callable
from typing import Final

from lens_common.logging import get_logger

__all__ = [
    "GracefulShutdown",
    "ShutdownHook",
]

ShutdownHook = Callable[[], Awaitable[None]]

_SHUTDOWN_TIMEOUT: Final[float] = 30.0


class GracefulShutdown:
    def __init__(self) -> None:
        self._hooks: list[ShutdownHook] = []
        self._logger = get_logger(__name__)
        self._shutdown_event = asyncio.Event()

    @property
    def should_exit(self) -> bool:
        return self._shutdown_event.is_set()

    @property
    def shutdown_event(self) -> asyncio.Event:
        return self._shutdown_event

    def register(self, hook: ShutdownHook) -> None:
        self._hooks.append(hook)

    def setup_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._trigger)

    def _trigger(self) -> None:
        self._logger.info("shutdown_signal_received")
        self._shutdown_event.set()

    async def wait(self) -> None:
        await self._shutdown_event.wait()

    async def shutdown(self) -> None:
        self._logger.info("shutdown_started", hook_count=len(self._hooks))
        for hook in self._hooks:
            try:
                await asyncio.wait_for(hook(), timeout=_SHUTDOWN_TIMEOUT)
            except Exception:
                self._logger.warning("shutdown_hook_failed", exc_info=True)
        self._logger.info("shutdown_complete")
