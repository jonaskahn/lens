"""Apprise-backed :class:`NotifierPort` implementation.

Wraps the :mod:`apprise` library. The Apprise URL is supplied per-send
(the notifier does not own long-lived channel state - the channel entity
holds the encrypted URL and the use case decrypts it just before the
send call). The implementation never logs the decrypted URL.

A :class:`LoggingNotifier` is provided as a test / dry-run adapter: it
captures every send into an in-memory list so the test suite can assert
on the rendered bodies without depending on a working Apprise transport.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from lens_application.pipeline import (
    RenderedMessage,
    SendResult,
)

__all__ = [
    "AppriseNotifier",
    "LoggingNotifier",
    "NotificationError",
]


_logger = logging.getLogger("lens_notifier")


class NotificationError(RuntimeError):
    """Raised when the underlying transport (Apprise) fails unrecoverably."""


@dataclass
class LoggingNotifier:
    """A test / dev notifier that records every send in ``sent``."""

    sent: list[dict[str, Any]] = field(default_factory=list)
    fail_for: set[str] = field(default_factory=set)

    async def send(
        self,
        *,
        channel_kind: str,
        apprise_url: str,
        message: RenderedMessage,
    ) -> SendResult:
        record = {
            "channel_kind": channel_kind,
            "apprise_url": apprise_url,
            "subject": message.subject,
            "body": message.body,
            "template": message.template,
        }
        self.sent.append(record)
        if apprise_url in self.fail_for:
            return SendResult(success=False, error="simulated failure")
        return SendResult(success=True)


class AppriseNotifier:
    """An :class:`Apprise`-backed :class:`NotifierPort`.

    Apprise is imported lazily so the dependency is not required at test
    time; the production notifier-worker image installs ``apprise``.
    """

    def __init__(self, *, timeout_seconds: int = 10) -> None:
        self._timeout = timeout_seconds

    async def send(
        self,
        *,
        channel_kind: str,
        apprise_url: str,
        message: RenderedMessage,
    ) -> SendResult:
        try:
            import apprise
        except ImportError as exc:  # pragma: no cover
            raise NotificationError(
                "apprise is not installed; cannot send notifications",
            ) from exc
        apprise_obj = apprise.Apprise()
        added = apprise_obj.add(apprise_url)
        if not added:
            return SendResult(success=False, error="apprise_url rejected by apprise")
        _logger.info(
            "sending notification kind=%s template=%s subject=%s",
            channel_kind,
            message.template,
            message.subject,
        )
        try:
            notified = apprise_obj.notify(
                body=message.body,
                title=message.subject,
            )
        except Exception as exc:
            return SendResult(success=False, error=f"apraise raised: {exc}")
        if not notified:
            return SendResult(success=False, error="apprise reported no recipients")
        return SendResult(success=True)
