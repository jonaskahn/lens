"""Outbox relay.

A small loop that calls :class:`lens_application.use_cases.PublishOutboxUseCase`
periodically and lets the application layer decide how the broker
publisher is wired. The relay lives in infrastructure (not application)
because it owns the scheduling + broker glue; the use case is the
business rule ("drain the outbox").
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from lens_application.use_cases import PublishOutboxUseCase
from lens_common.logging import get_logger

__all__ = ["OutboxRelay", "OutboxRelaySettings", "run_outbox_relay"]


_logger = get_logger("lens_outbox_relay")


@dataclass(frozen=True, slots=True)
class OutboxRelaySettings:
    """Operational knobs for the outbox relay loop."""

    tick_seconds: float = 1.0
    batch_size: int = 100


class OutboxRelay:
    """An outbox relay that drives the :class:`PublishOutboxUseCase` in a loop."""

    def __init__(
        self,
        uow_factory: Any,
        publisher: Any,
        settings: OutboxRelaySettings | None = None,
    ) -> None:
        self._use_case = PublishOutboxUseCase(
            uow_factory,
            publisher,
            batch_size=(settings or OutboxRelaySettings()).batch_size,
        )
        self._settings = settings or OutboxRelaySettings()
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        """Signal the relay loop to exit at the next tick boundary."""
        self._stop.set()

    async def run(self) -> None:
        """Run the relay loop until :meth:`request_stop` is called."""
        _logger.info(
            "outbox relay started (tick=%.2fs, batch=%d)",
            self._settings.tick_seconds,
            self._settings.batch_size,
        )
        while not self._stop.is_set():
            try:
                stats = await self._use_case.execute({})
                if stats["published"] or stats["failed"]:
                    _logger.info(
                        "outbox tick: published=%d failed=%d",
                        stats["published"],
                        stats["failed"],
                    )
            except Exception:
                _logger.exception("outbox tick failed; continuing")
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self._settings.tick_seconds,
                )
            except TimeoutError:
                continue
        _logger.info("outbox relay stopped")


async def run_outbox_relay(
    uow_factory: Any,
    publisher: Any,
    settings: OutboxRelaySettings | None = None,
) -> None:
    """Module-level convenience wrapper for the relay loop."""
    relay = OutboxRelay(uow_factory, publisher, settings)
    await relay.run()
