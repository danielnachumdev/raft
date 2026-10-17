"""Declared metric keys for resources and HTTP alert sources."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class MetricKey:
    key: str
    label: str
    unit: str
    scopes: Tuple[str, ...]


RESOURCE_METRICS: Tuple[MetricKey, ...] = (
    MetricKey("cpu_percent", "CPU percent", "percent", ("host", "service")),
    MetricKey("memory_used_percent", "Memory used percent", "percent", ("host", "service")),
    MetricKey("memory_used_bytes", "Memory used bytes", "bytes", ("host", "service")),
    MetricKey("memory_limit_bytes", "Memory limit bytes", "bytes", ("service",)),
    MetricKey("pids", "PIDs", "count", ("service",)),
    MetricKey("uptime_seconds", "Uptime seconds", "seconds", ("service",)),
    MetricKey("network_rx_bytes", "Network RX bytes", "bytes", ("service",)),
    MetricKey("network_tx_bytes", "Network TX bytes", "bytes", ("service",)),
    MetricKey("block_read_bytes", "Block read bytes", "bytes", ("service",)),
    MetricKey("block_write_bytes", "Block write bytes", "bytes", ("service",)),
)

HTTP_METRICS: Tuple[MetricKey, ...] = (
    MetricKey("rps", "Requests per second", "rps", ("edge", "service")),
    MetricKey("requests", "Requests", "count", ("edge", "service")),
    MetricKey("duration_avg_ms", "Avg duration ms", "ms", ("edge", "service")),
    MetricKey("duration_p50_ms", "p50 duration ms", "ms", ("edge", "service")),
    MetricKey("duration_p95_ms", "p95 duration ms", "ms", ("edge", "service")),
    MetricKey("duration_p99_ms", "p99 duration ms", "ms", ("edge", "service")),
    MetricKey("status_2xx", "2xx responses", "count", ("edge", "service")),
    MetricKey("status_3xx", "3xx responses", "count", ("edge", "service")),
    MetricKey("status_4xx", "4xx responses", "count", ("edge", "service")),
    MetricKey("status_5xx", "5xx responses", "count", ("edge", "service")),
    MetricKey("error_rate_5xx", "5xx error rate", "ratio", ("edge", "service")),
    MetricKey("error_rate_4xx", "4xx error rate", "ratio", ("edge", "service")),
    MetricKey("in_flight", "In-flight requests", "count", ("edge",)),
    MetricKey("active_connections", "Active connections", "count", ("edge",)),
)
