"""Minimal composition-root / DI helpers.

We deliberately keep this small. A :class:`Container` is just a typed dict
that lets composition roots register factories; the application code receives
its dependencies through constructor parameters and never touches the
container directly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = [
    "Container",
    "Scope",
]


class Container:
    """A tiny DI container keyed by an interface type.

    Each app's composition root builds one of these and passes factories that
    return the concrete adapters. Business code never imports this class.
    """

    def __init__(self) -> None:
        self._factories: dict[type[Any], Callable[[Container], Any]] = {}
        self._singletons: dict[type[Any], Any] = {}
        self._singleton_flags: dict[type[Any], bool] = {}

    def register(
        self,
        interface: type[Any],
        factory: Callable[[Container], Any],
        *,
        singleton: bool = True,
    ) -> None:
        """Bind ``interface`` to a factory.

        When ``singleton`` is true (default), the factory runs at most once and
        the same instance is returned for subsequent calls. When ``singleton``
        is false, the factory is invoked on every :meth:`resolve` call.
        """
        self._factories[interface] = factory
        self._singletons.pop(interface, None)
        self._singleton_flags[interface] = singleton

    def resolve(self, interface: type[Any]) -> Any:
        """Build or retrieve the registered instance for ``interface``."""
        if interface not in self._factories:
            raise KeyError(f"no factory registered for {interface!r}")
        if self._singleton_flags.get(interface, True) and interface in self._singletons:
            return self._singletons[interface]
        instance = self._factories[interface](self)
        if self._singleton_flags.get(interface, True):
            self._singletons[interface] = instance
        return instance

    def override(self, interface: type[Any], instance: Any) -> None:
        """Replace the registered singleton with ``instance`` (used in tests)."""
        self._factories[interface] = lambda _c: instance
        self._singletons[interface] = instance
        self._singleton_flags[interface] = True


def make_container() -> Container:
    """Build an empty :class:`Container`."""
    return Container()


Scope = Container
"""Alias used in composition roots to clarify intent."""
