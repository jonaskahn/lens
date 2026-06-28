"""Prometheus metrics primitives."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

from lens_common.metrics import (
    MetricFactory,
    Metrics,
    create_metrics,
    generate_latest_metrics,
)


class TestMetrics:
    def test_default_prefix(self) -> None:
        m = Metrics()
        assert m._prefix == "lens"
        assert isinstance(m.registry, CollectorRegistry)

    def test_custom_prefix(self) -> None:
        m = Metrics(prefix="test")
        assert m._prefix == "test"
        c = m.counter("errors", "desc")
        assert c._name == "test_errors"

    def test_shared_registry(self) -> None:
        registry = CollectorRegistry()
        m1 = Metrics(registry=registry)
        m2 = Metrics(registry=registry)
        assert m1.registry is m2.registry

    def test_counter_with_labels(self) -> None:
        m = Metrics()
        c = m.counter("ops", "Operations", labelnames=["app"])
        assert isinstance(c, Counter)
        assert c._name == "lens_ops"

    def test_gauge_with_labels(self) -> None:
        m = Metrics()
        g = m.gauge("temp", "Temperature", labelnames=["sensor"])
        assert isinstance(g, Gauge)
        assert g._name == "lens_temp"

    def test_histogram_default_buckets(self) -> None:
        m = Metrics()
        h = m.histogram("latency", "Latency ms")
        assert isinstance(h, Histogram)
        assert h._name == "lens_latency"

    def test_histogram_custom_buckets(self) -> None:
        m = Metrics()
        h = m.histogram("latency", "Latency", buckets=[0.5, 1, 5])
        assert isinstance(h, Histogram)

    def test_fqn_format(self) -> None:
        m = Metrics(prefix="app")
        assert m._fqn("counter") == "app_counter"


class TestMetricFactory:
    def test_creates_all_canonical_metrics(self) -> None:
        m = Metrics()
        factory = MetricFactory(m)
        assert isinstance(factory.task_processed, Counter)
        assert isinstance(factory.crawl_duration_seconds, Histogram)
        assert isinstance(factory.diff_outcome, Counter)
        assert isinstance(factory.notification_result, Counter)
        assert isinstance(factory.lease_contention, Counter)
        assert isinstance(factory.throttle_wait_seconds, Histogram)
        assert isinstance(factory.dlq_count, Gauge)
        assert isinstance(factory.in_flight, Gauge)
        assert isinstance(factory.queue_depth, Gauge)
        assert isinstance(factory.tick_duration_seconds, Histogram)
        assert isinstance(factory.enrichment_duration_ms, Histogram)
        assert isinstance(factory.classification_result, Counter)
        assert isinstance(factory.llm_tokens_total, Counter)

    def test_registry_property_returns_metrics_registry(self) -> None:
        m = Metrics()
        factory = MetricFactory(m)
        assert factory.registry is m.registry


class TestCreateMetrics:
    def test_returns_metrics_instance(self) -> None:
        m = create_metrics(prefix="svc")
        assert isinstance(m, Metrics)
        assert m._prefix == "svc"

    def test_with_registry(self) -> None:
        registry = CollectorRegistry()
        m = create_metrics(registry=registry)
        assert m.registry is registry


class TestGenerateLatestMetrics:
    def test_returns_bytes(self) -> None:
        result = generate_latest_metrics()
        assert isinstance(result, bytes)

    def test_with_custom_registry(self) -> None:
        registry = CollectorRegistry()
        result = generate_latest_metrics(registry)
        assert isinstance(result, bytes)
