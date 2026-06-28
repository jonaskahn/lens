"""DI container: override, make_container, resolve edge cases."""

from __future__ import annotations

from lens_common.di import Container, make_container


def test_make_container_returns_empty_container() -> None:
    c = make_container()
    assert isinstance(c, Container)


def test_override_replaces_singleton() -> None:
    container = Container()

    class Service:
        def __init__(self, name: str = "original") -> None:
            self.name = name

    container.register(Service, lambda _: Service("original"), singleton=True)
    original = container.resolve(Service)
    assert original.name == "original"

    container.override(Service, Service("overridden"))
    overridden = container.resolve(Service)
    assert overridden.name == "overridden"


def test_override_sets_singleton_flag() -> None:
    container = Container()

    class Service:
        pass

    container.register(Service, lambda _: Service(), singleton=False)
    a = container.resolve(Service)
    b = container.resolve(Service)
    assert a is not b

    container.override(Service, Service())
    c1 = container.resolve(Service)
    c2 = container.resolve(Service)
    assert c1 is c2
