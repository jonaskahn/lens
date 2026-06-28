"""Ports, DI container, pagination types."""

from __future__ import annotations

from uuid import UUID

import pytest

from lens_common.di import Container
from lens_common.ports import SystemClock, UuidV7Generator
from lens_common.types import Page, PageRequest


def test_given_system_clock_when_now_then_is_utc_aware() -> None:
    clock = SystemClock()
    now = clock.now()
    assert now.tzinfo is not None
    assert now.utcoffset() is not None


def test_given_uuidv7_generator_when_new_then_returns_uuid7() -> None:
    gen = UuidV7Generator()
    value = gen.new()
    assert isinstance(value, UUID)
    assert value.version == 7


def test_given_container_with_factory_when_resolve_then_returns_singleton() -> None:
    container = Container()

    class Counter:
        def __init__(self) -> None:
            self.n = 0

    container.register(Counter, lambda _: Counter(), singleton=True)
    a = container.resolve(Counter)
    b = container.resolve(Counter)
    assert a is b


def test_given_container_with_non_singleton_when_resolve_then_creates_new() -> None:
    container = Container()

    class Counter:
        def __init__(self) -> None:
            self.n = 0

    container.register(Counter, lambda _: Counter(), singleton=False)
    a = container.resolve(Counter)
    b = container.resolve(Counter)
    assert a is not b


def test_given_container_without_factory_when_resolve_then_raises() -> None:
    container = Container()
    with pytest.raises(KeyError, match="no factory registered"):
        container.resolve(object)


def test_given_page_request_when_defaults_then_limit_50_no_cursor() -> None:
    req = PageRequest()
    assert req.cursor is None
    assert req.limit == 50


def test_given_page_when_iter_then_yields_items_in_order() -> None:
    page: Page[int] = Page(items=[1, 2, 3], next_cursor="abc")
    assert list(page) == [1, 2, 3]
    assert page.next_cursor == "abc"


def test_given_page_when_empty_then_iter_is_empty() -> None:
    page: Page[str] = Page(items=[], next_cursor=None)
    assert list(page) == []
