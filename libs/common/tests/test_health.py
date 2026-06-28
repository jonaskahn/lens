"""Health check infrastructure."""

from __future__ import annotations

from lens_common.health import ComponentStatus, HealthCheck, HealthStatus


async def _healthy() -> ComponentStatus:
    return ComponentStatus(healthy=True, details={"db": "ok"})


async def _unhealthy() -> ComponentStatus:
    return ComponentStatus(healthy=False, details={"db": "down"})


async def _raises() -> ComponentStatus:
    raise RuntimeError("boom")


class TestHealthCheck:
    async def test_health_when_all_healthy_then_returns_healthy(self) -> None:
        hc = HealthCheck()
        hc.add_check("db", _healthy)
        result = await hc.health()
        assert result.healthy is True
        assert result.components["db"].healthy is True
        assert result.components["db"].details == {"db": "ok"}

    async def test_health_when_one_unhealthy_then_returns_unhealthy(self) -> None:
        hc = HealthCheck()
        hc.add_check("db", _unhealthy)
        result = await hc.health()
        assert result.healthy is False
        assert result.components["db"].healthy is False

    async def test_health_when_check_raises_then_marked_unhealthy(self) -> None:
        hc = HealthCheck()
        hc.add_check("db", _raises)
        result = await hc.health()
        assert result.healthy is False
        assert result.components["db"].healthy is False
        assert "boom" in result.components["db"].details["error"]

    async def test_ready_when_all_ready_checks_pass_then_healthy(self) -> None:
        hc = HealthCheck()
        hc.add_ready_check("db", _healthy)
        result = await hc.ready()
        assert result.healthy is True

    async def test_ready_when_no_checks_then_empty_healthy(self) -> None:
        hc = HealthCheck()
        result = await hc.ready()
        assert result.healthy is True
        assert result.components == {}

    async def test_health_when_no_checks_then_empty_healthy(self) -> None:
        hc = HealthCheck()
        result = await hc.health()
        assert result.healthy is True
        assert result.components == {}

    async def test_multiple_checks_mixed_outcomes_then_unhealthy(self) -> None:
        hc = HealthCheck()
        hc.add_check("db", _healthy)
        hc.add_check("cache", _unhealthy)
        result = await hc.health()
        assert result.healthy is False
        assert result.components["db"].healthy is True
        assert result.components["cache"].healthy is False


def test_health_status_default() -> None:
    hs = HealthStatus(healthy=True)
    assert hs.healthy is True
    assert hs.components == {}

    hs2 = HealthStatus(healthy=False)
    assert hs2.healthy is False


def test_component_status_default() -> None:
    cs = ComponentStatus(healthy=True)
    assert cs.healthy is True
    assert cs.details == {}
