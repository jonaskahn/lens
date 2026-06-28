"""Prometheus metrics primitives.

Each :class:`Metrics` instance owns a private :class:`CollectorRegistry` by default so that
constructing multiple metric factories in the same process (multi-role composition, tests,
dynamic-config reload) does not raise ``Duplicated timeseries``. Callers that need to share a
registry across factories should pass the same registry explicitly to :func:`create_metrics`.
"""

from __future__ import annotations

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

__all__ = [
    "MetricFactory",
    "Metrics",
    "create_metrics",
    "generate_latest_metrics",
]


class Metrics:
    """Build Prometheus collectors against a private :class:`CollectorRegistry`."""

    def __init__(
        self,
        *,
        prefix: str = "lens",
        registry: CollectorRegistry | None = None,
    ) -> None:
        self._prefix = prefix
        self._registry = registry if registry is not None else CollectorRegistry()

    @property
    def registry(self) -> CollectorRegistry:
        return self._registry

    def counter(
        self,
        name: str,
        description: str,
        *,
        labelnames: list[str] | None = None,
    ) -> Counter:
        return Counter(
            self._fqn(name),
            description,
            labelnames=labelnames or [],
            registry=self._registry,
        )

    def gauge(
        self,
        name: str,
        description: str,
        *,
        labelnames: list[str] | None = None,
    ) -> Gauge:
        return Gauge(
            self._fqn(name),
            description,
            labelnames=labelnames or [],
            registry=self._registry,
        )

    def histogram(
        self,
        name: str,
        description: str,
        *,
        labelnames: list[str] | None = None,
        buckets: list[float] | None = None,
    ) -> Histogram:
        if buckets is None:
            return Histogram(
                self._fqn(name),
                description,
                labelnames=labelnames or [],
                registry=self._registry,
            )
        return Histogram(
            self._fqn(name),
            description,
            labelnames=labelnames or [],
            buckets=buckets,
            registry=self._registry,
        )

    def _fqn(self, name: str) -> str:
        return f"{self._prefix}_{name}"


class MetricFactory:
    """Eagerly-register the canonical lens metric set against a private registry."""

    def __init__(self, metrics: Metrics) -> None:
        self._metrics = metrics

        self.task_processed: Counter = metrics.counter(
            "task_processed_total",
            "Tasks processed by outcome",
            labelnames=["app", "outcome"],
        )
        self.crawl_duration_seconds: Histogram = metrics.histogram(
            "crawl_duration_seconds",
            "Crawl fetch + process duration",
            labelnames=["app"],
            buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
        )
        self.diff_outcome: Counter = metrics.counter(
            "diff_outcome_total",
            "Diff result outcomes",
            labelnames=["app", "outcome"],
        )
        self.notification_result: Counter = metrics.counter(
            "notification_result_total",
            "Notification send results",
            labelnames=["app", "channel_kind", "outcome"],
        )
        self.lease_contention: Counter = metrics.counter(
            "lease_contention_total",
            "Lease acquire misses",
            labelnames=["app"],
        )
        self.throttle_wait_seconds: Histogram = metrics.histogram(
            "throttle_wait_seconds",
            "Time spent waiting for throttle tokens",
            labelnames=["app"],
            buckets=[0.1, 0.5, 1, 5, 10, 30, 60],
        )
        self.dlq_count: Gauge = metrics.gauge(
            "dlq_messages",
            "Messages currently in dead-letter queues",
            labelnames=["queue"],
        )
        self.in_flight: Gauge = metrics.gauge(
            "in_flight_tasks",
            "Tasks currently being processed",
            labelnames=["app"],
        )
        self.queue_depth: Gauge = metrics.gauge(
            "queue_depth",
            "Approximate queue depth",
            labelnames=["queue"],
        )
        self.tick_duration_seconds: Histogram = metrics.histogram(
            "tick_duration_seconds",
            "Scheduler tick duration",
            labelnames=["app"],
            buckets=[0.1, 0.5, 1, 2, 5, 10],
        )
        self.enrichment_duration_ms: Histogram = metrics.histogram(
            "enrichment_duration_ms",
            "LLM enrichment processing latency",
            labelnames=["app"],
            buckets=[100, 500, 1000, 2500, 5000, 10000, 30000],
        )
        self.classification_result: Counter = metrics.counter(
            "classification_result_total",
            "Classification outcomes by change type",
            labelnames=["app", "change_type"],
        )
        self.llm_tokens_total: Counter = metrics.counter(
            "llm_tokens_total",
            "Total LLM tokens consumed",
            labelnames=["app"],
        )

    @property
    def registry(self) -> CollectorRegistry:
        return self._metrics.registry


def generate_latest_metrics(registry: CollectorRegistry | None = None) -> bytes:
    r = registry if registry is not None else REGISTRY
    return generate_latest(r)


def create_metrics(
    prefix: str = "lens",
    *,
    registry: CollectorRegistry | None = None,
) -> Metrics:
    return Metrics(prefix=prefix, registry=registry)
