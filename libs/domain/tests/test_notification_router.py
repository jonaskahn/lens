"""Tests for the :class:`NotificationRouter` domain service."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from lens_domain.entities import Channel, ChannelBinding
from lens_domain.enums import BindingScope, ChannelKind, TriggerType
from lens_domain.errors import NoChannelsBound
from lens_domain.services import NotificationRouter, RouterRequest


def _channel(name: str, *, enabled: bool = True) -> Channel:
    now = datetime(2026, 1, 1)
    return Channel.create(
        id=uuid4(),
        name=name,
        kind=ChannelKind.WEBHOOK,
        apprise_url=f"json://localhost/{name}",
        enabled=enabled,
        now=now,
    )


def _binding(
    channel_id: UUID,
    scope: BindingScope,
    *,
    scope_id: UUID | None = None,
    on_change: bool = True,
    on_error: bool = False,
    on_no_change: bool = False,
) -> ChannelBinding:
    now = datetime(2026, 1, 1)
    return ChannelBinding.create(
        id=uuid4(),
        channel_id=channel_id,
        scope=scope,
        scope_id=scope_id,
        on_change=on_change,
        on_error=on_error,
        on_no_change=on_no_change,
        now=now,
    )


def _request(
    *,
    url_id: UUID,
    domain_id: UUID,
    category_id: UUID | None,
    trigger: TriggerType,
    bindings: list[ChannelBinding],
    channels: list[Channel],
) -> RouterRequest:
    return RouterRequest(
        url_id=url_id,
        domain_id=domain_id,
        category_id=category_id,
        trigger=trigger,
        bindings=tuple(bindings),
        channels={c.id: c for c in channels},
    )


def test_given_no_bindings_when_route_then_returns_empty_list() -> None:
    request = _request(
        url_id=uuid4(),
        domain_id=uuid4(),
        category_id=None,
        trigger=TriggerType.ON_CHANGE,
        bindings=[],
        channels=[],
    )

    result = NotificationRouter().route(request)

    assert result == []


def test_given_global_binding_when_route_then_includes_channel() -> None:
    domain_id = uuid4()
    channel = _channel("global")
    binding = _binding(channel.id, BindingScope.GLOBAL)
    request = _request(
        url_id=uuid4(),
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_CHANGE,
        bindings=[binding],
        channels=[channel],
    )

    result = NotificationRouter().route(request)

    assert result == [channel]


def test_given_domain_binding_when_route_then_includes_channel() -> None:
    domain_id = uuid4()
    channel = _channel("domain")
    binding = _binding(channel.id, BindingScope.DOMAIN, scope_id=domain_id)
    request = _request(
        url_id=uuid4(),
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_CHANGE,
        bindings=[binding],
        channels=[channel],
    )

    result = NotificationRouter().route(request)

    assert result == [channel]


def test_given_category_binding_when_route_then_includes_channel() -> None:
    domain_id = uuid4()
    category_id = uuid4()
    channel = _channel("category")
    binding = _binding(channel.id, BindingScope.CATEGORY, scope_id=category_id)
    request = _request(
        url_id=uuid4(),
        domain_id=domain_id,
        category_id=category_id,
        trigger=TriggerType.ON_CHANGE,
        bindings=[binding],
        channels=[channel],
    )

    result = NotificationRouter().route(request)

    assert result == [channel]


def test_given_url_binding_when_route_then_includes_channel() -> None:
    domain_id = uuid4()
    url_id = uuid4()
    channel = _channel("url")
    binding = _binding(channel.id, BindingScope.URL, scope_id=url_id)
    request = _request(
        url_id=url_id,
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_CHANGE,
        bindings=[binding],
        channels=[channel],
    )

    result = NotificationRouter().route(request)

    assert result == [channel]


def test_given_url_and_global_for_same_channel_when_route_then_keeps_url_only() -> None:
    domain_id = uuid4()
    url_id = uuid4()
    channel = _channel("shared")
    bindings = [
        _binding(channel.id, BindingScope.GLOBAL),
        _binding(channel.id, BindingScope.URL, scope_id=url_id),
    ]
    request = _request(
        url_id=url_id,
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_CHANGE,
        bindings=bindings,
        channels=[channel],
    )

    result = NotificationRouter().route(request)

    assert result == [channel]


def test_given_layered_bindings_when_route_then_preserves_most_specific_first() -> None:
    domain_id = uuid4()
    category_id = uuid4()
    url_id = uuid4()
    url_channel = _channel("url-only")
    cat_channel = _channel("cat-only")
    domain_channel = _channel("domain-only")
    global_channel = _channel("global-only")
    bindings = [
        _binding(global_channel.id, BindingScope.GLOBAL),
        _binding(domain_channel.id, BindingScope.DOMAIN, scope_id=domain_id),
        _binding(cat_channel.id, BindingScope.CATEGORY, scope_id=category_id),
        _binding(url_channel.id, BindingScope.URL, scope_id=url_id),
    ]
    request = _request(
        url_id=url_id,
        domain_id=domain_id,
        category_id=category_id,
        trigger=TriggerType.ON_CHANGE,
        bindings=bindings,
        channels=[url_channel, cat_channel, domain_channel, global_channel],
    )

    result = NotificationRouter().route(request)

    assert result == [url_channel, cat_channel, domain_channel, global_channel]


def test_given_duplicate_bindings_at_same_scope_when_route_then_dedupes() -> None:
    domain_id = uuid4()
    channel = _channel("dup")
    bindings = [
        _binding(channel.id, BindingScope.DOMAIN, scope_id=domain_id),
        _binding(channel.id, BindingScope.DOMAIN, scope_id=domain_id),
    ]
    request = _request(
        url_id=uuid4(),
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_CHANGE,
        bindings=bindings,
        channels=[channel],
    )

    result = NotificationRouter().route(request)

    assert result == [channel]


def test_given_trigger_mismatch_when_route_then_excludes_binding() -> None:
    domain_id = uuid4()
    channel = _channel("error-only")
    binding = _binding(
        channel.id,
        BindingScope.GLOBAL,
        on_change=False,
        on_error=True,
    )
    request = _request(
        url_id=uuid4(),
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_CHANGE,
        bindings=[binding],
        channels=[channel],
    )

    result = NotificationRouter().route(request)

    assert result == []


def test_given_error_trigger_when_route_then_includes_error_binding() -> None:
    domain_id = uuid4()
    channel = _channel("errors")
    binding = _binding(
        channel.id,
        BindingScope.GLOBAL,
        on_change=False,
        on_error=True,
    )
    request = _request(
        url_id=uuid4(),
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_ERROR,
        bindings=[binding],
        channels=[channel],
    )

    result = NotificationRouter().route(request)

    assert result == [channel]


def test_given_disabled_channel_when_route_then_excludes_channel() -> None:
    domain_id = uuid4()
    enabled = _channel("enabled")
    disabled = _channel("disabled", enabled=False)
    bindings = [
        _binding(enabled.id, BindingScope.GLOBAL),
        _binding(disabled.id, BindingScope.GLOBAL),
    ]
    request = _request(
        url_id=uuid4(),
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_CHANGE,
        bindings=bindings,
        channels=[enabled, disabled],
    )

    result = NotificationRouter().route(request)

    assert result == [enabled]


def test_given_channel_not_loaded_when_route_then_skips_binding() -> None:
    domain_id = uuid4()
    missing_id = uuid4()
    binding = _binding(missing_id, BindingScope.GLOBAL)
    request = _request(
        url_id=uuid4(),
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_CHANGE,
        bindings=[binding],
        channels=[],
    )

    result = NotificationRouter().route(request)

    assert result == []


def test_given_binding_for_other_url_when_route_then_excludes_binding() -> None:
    domain_id = uuid4()
    other_url_id = uuid4()
    channel = _channel("other-url")
    binding = _binding(channel.id, BindingScope.URL, scope_id=other_url_id)
    request = _request(
        url_id=uuid4(),
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_CHANGE,
        bindings=[binding],
        channels=[channel],
    )

    result = NotificationRouter().route(request)

    assert result == []


def test_given_on_no_change_trigger_when_route_then_includes_matching_binding() -> None:
    domain_id = uuid4()
    channel = _channel("staleness")
    binding = _binding(
        channel.id,
        BindingScope.GLOBAL,
        on_change=False,
        on_error=False,
        on_no_change=True,
    )
    request = _request(
        url_id=uuid4(),
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_NO_CHANGE,
        bindings=[binding],
        channels=[channel],
    )

    result = NotificationRouter().route(request)

    assert result == [channel]


def test_given_url_and_category_bindings_for_different_channels_when_route_then_keeps_both() -> None:
    domain_id = uuid4()
    category_id = uuid4()
    url_id = uuid4()
    url_channel = _channel("url")
    cat_channel = _channel("cat")
    bindings = [
        _binding(url_channel.id, BindingScope.URL, scope_id=url_id),
        _binding(cat_channel.id, BindingScope.CATEGORY, scope_id=category_id),
    ]
    request = _request(
        url_id=url_id,
        domain_id=domain_id,
        category_id=category_id,
        trigger=TriggerType.ON_CHANGE,
        bindings=bindings,
        channels=[url_channel, cat_channel],
    )

    result = NotificationRouter().route(request)

    assert result == [url_channel, cat_channel]


def test_given_invalid_scope_string_when_route_then_skips_binding() -> None:
    domain_id = uuid4()
    channel = _channel("weird")
    valid = _binding(channel.id, BindingScope.GLOBAL)
    request = _request(
        url_id=uuid4(),
        domain_id=domain_id,
        category_id=None,
        trigger=TriggerType.ON_CHANGE,
        bindings=[valid],
        channels=[channel],
    )

    result = NotificationRouter().route(request)

    assert result == [channel]


def test_no_channels_bound_is_a_domain_error() -> None:
    from lens_common.errors import DomainError

    assert issubclass(NoChannelsBound, DomainError)
