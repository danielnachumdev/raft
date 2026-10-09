"""Unit tests for HttpMetricsAggregator."""

from __future__ import annotations

from raft.controller.http_metrics_agg import HttpMetricsAggregator


class TestHttpMetricsAggregator:
    def test_aggregate_edge_and_by_service(self) -> None:
        sample = HttpMetricsAggregator().aggregate(
            [
                "0.010 200 demo-api.test",
                "0.020 200 demo-api.test",
                "0.100 500 other.test",
                "not-a-log-line",
            ],
            interval_seconds=2.0,
            in_flight=3,
            active_connections=5,
            host_to_service={"demo-api.test": "demo-api"},
        )
        assert sample["requests"] == 3 and sample["rps"] == 1.5
        assert sample["in_flight"] == 3 and sample["status_class"]["5xx"] == 1
        assert sample["by_service"]["demo-api"]["requests"] == 2

    def test_percentiles_empty(self) -> None:
        assert HttpMetricsAggregator.percentiles([]) == {
            "avg": None,
            "p50": None,
            "p95": None,
            "p99": None,
        }

    def test_percentiles_single(self) -> None:
        out = HttpMetricsAggregator.percentiles([42.0])
        assert out["avg"] == 42.0 and out["p99"] == 42.0

    def test_parse_line_rejects_short(self) -> None:
        assert HttpMetricsAggregator.parse_line("1.0 200") is None
        assert HttpMetricsAggregator.parse_line("x 200 host") is None
        assert HttpMetricsAggregator.parse_line("0.1 200 -") is None

    def test_status_class_buckets(self) -> None:
        sample = HttpMetricsAggregator().aggregate(
            ["0.01 301 h.test", "0.01 404 h.test", "0.01 199 h.test"],
            interval_seconds=1.0,
            in_flight=None,
            active_connections=None,
            host_to_service={},
        )
        assert sample["status_class"]["3xx"] == 1
        assert sample["status_class"]["4xx"] == 1
        assert sample["status_class"]["other"] == 1
