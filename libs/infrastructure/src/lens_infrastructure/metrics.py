from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram


class InfrastructureMetrics:
    def __init__(self, *, prefix: str = "lens") -> None:
        self._prefix = prefix

        self.db_query_duration_seconds: Histogram = Histogram(
            f"{prefix}_db_query_duration_seconds",
            "Database query duration",
            labelnames=["operation"],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1],
        )
        self.broker_publish_total: Counter = Counter(
            f"{prefix}_broker_publish_total",
            "Broker messages published",
            labelnames=["exchange", "routing_key"],
        )
        self.broker_consume_total: Counter = Counter(
            f"{prefix}_broker_consume_total",
            "Broker messages consumed",
            labelnames=["queue"],
        )
        self.crawler_fetch_duration_seconds: Histogram = Histogram(
            f"{prefix}_crawler_fetch_duration_seconds",
            "crawl4ai fetch duration",
            buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
        )
        self.crawler_fetch_outcome: Counter = Counter(
            f"{prefix}_crawler_fetch_outcome_total",
            "crawl4ai fetch outcomes",
            labelnames=["outcome"],
        )
        self.notifier_send_total: Counter = Counter(
            f"{prefix}_notifier_send_total",
            "Notification send attempts",
            labelnames=["channel_kind", "outcome"],
        )
        self.lease_acquire_total: Counter = Counter(
            f"{prefix}_lease_acquire_total",
            "Lease acquire attempts",
            labelnames=["outcome"],
        )
        self.throttle_blocked_total: Counter = Counter(
            f"{prefix}_throttle_blocked_total",
            "Throttle blocks",
            labelnames=["host"],
        )
        self.queue_depth_gauge: Gauge = Gauge(
            f"{prefix}_queue_depth",
            "Approximate queue depth",
            labelnames=["queue"],
        )


def create_infrastructure_metrics(prefix: str = "lens") -> InfrastructureMetrics:
    return InfrastructureMetrics(prefix=prefix)
