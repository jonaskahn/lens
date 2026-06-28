"""Channel secret provider.

A thin adapter the application layer can use to obtain a channel's
Apprise URL. The implementation simply forwards the already-decrypted
URL from the :class:`Channel` entity. It can be swapped for a vault /
KMS lookup without touching the use case that consumes the protocol.
"""

from __future__ import annotations

from lens_application.pipeline import ChannelSecretProvider as _ChannelSecretProviderProtocol
from lens_domain.entities import Channel

__all__ = ["ChannelSecretProvider"]


class ChannelSecretProvider(_ChannelSecretProviderProtocol):
    """Default :class:`_ChannelSecretProviderProtocol` using the entity's URL field."""

    def apprise_url_for(self, channel: Channel) -> str:
        return channel.apprise_url
