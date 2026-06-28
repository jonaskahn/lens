from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any


@dataclass
class HealthStatus:
    healthy: bool
    components: dict[str, ComponentStatus] = field(default_factory=dict)


@dataclass
class ComponentStatus:
    healthy: bool
    details: dict[str, Any] = field(default_factory=dict)


class HealthCheck:
    def __init__(self) -> None:
        self._checks: dict[str, CheckFn] = {}
        self._ready_checks: dict[str, CheckFn] = {}

    def add_check(self, name: str, fn: CheckFn) -> None:
        self._checks[name] = fn

    def add_ready_check(self, name: str, fn: CheckFn) -> None:
        self._ready_checks[name] = fn

    async def health(self) -> HealthStatus:
        return await self._run_checks(self._checks)

    async def ready(self) -> HealthStatus:
        return await self._run_checks(self._ready_checks)

    async def _run_checks(self, checks: dict[str, CheckFn]) -> HealthStatus:
        components: dict[str, ComponentStatus] = {}
        all_healthy = True
        for name, fn in checks.items():
            try:
                result = await fn()
                components[name] = result
                if not result.healthy:
                    all_healthy = False
            except Exception as exc:
                components[name] = ComponentStatus(
                    healthy=False,
                    details={"error": str(exc)},
                )
                all_healthy = False
        return HealthStatus(healthy=all_healthy, components=components)


CheckFn = Callable[[], Coroutine[Any, Any, ComponentStatus]]
