"""HttpMetricSource with fixture JSONL."""

import json
from datetime import datetime, timezone
from pathlib import Path

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.alerts.signals.metrics.http_source import HttpMetricSource
from tests.unit.base import RaftTestCase

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


def _write_http_sample(path: Path) -> None:
    sample = {
        "ts": NOW.isoformat(),
        "requests": 100,
        "rps": 1.0,
        "duration_ms": {"avg": 10, "p50": 10, "p95": 20, "p99": 30},
        "status_class": {"2xx": 90, "3xx": 0, "4xx": 0, "5xx": 10, "other": 0},
        "by_service": {
            "demo-api": {
                "requests": 100,
                "rps": 1.0,
                "duration_ms": {"avg": 10, "p50": 10, "p95": 20, "p99": 30},
                "status_class": {"2xx": 90, "3xx": 0, "4xx": 0, "5xx": 10, "other": 0},
            }
        },
    }
    path.write_text(json.dumps(sample) + "\n", encoding="utf-8")


class TestHttpMetricSource(RaftTestCase):
    def _ctx(self) -> SignalContext:
        home = Path(self.tmp_path)
        path = MetricsPaths(home).http()
        path.parent.mkdir(parents=True)
        _write_http_sample(path)
        return SignalContext(home, NOW, app_names=["demo-api"])

    def test_error_rate_value(self) -> None:
        source = HttpMetricSource()
        series = source.query(
            {"target": "demo-api", "metric": "error_rate_5xx"},
            window_seconds=300,
            ctx=self._ctx(),
        )
        assert series[0].points[0].value == 0.1

    def test_validate_and_catalog(self) -> None:
        source = HttpMetricSource()
        issues = source.validate_select(
            {"target": "demo-api", "metric": "error_rate_5xx"}, path="s"
        )
        assert issues == []
        assert "HTTP" in source.catalog_entry()["label"]
