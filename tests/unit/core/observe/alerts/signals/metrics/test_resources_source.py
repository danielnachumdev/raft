"""ResourcesMetricSource with fixture JSONL."""

import json
from datetime import datetime, timezone
from pathlib import Path

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.alerts.signals.metrics.resources_source import (
    ResourcesMetricSource,
)
from tests.unit.base import RaftTestCase

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


_CONTAINER = {
    "service": "demo-api",
    "role": "app",
    "status": "running",
    "cpu_percent": 90.0,
    "memory": {"used_percent": 50, "used_bytes": 10, "limit_bytes": 20},
    "network": {"rx_bytes": 1, "tx_bytes": 2},
    "block_io": {"read_bytes": 3, "write_bytes": 4},
    "pids": 5,
    "uptime_seconds": 60,
}


def _sample() -> dict:
    return {
        "ts": NOW.isoformat(),
        "host": {
            "cpus": 2,
            "loadavg": [1.0, 1.0, 1.0],
            "memory": {"used_percent": 40, "used_bytes": 100},
        },
        "containers": [_CONTAINER],
    }


class TestResourcesMetricSource(RaftTestCase):
    def _ctx(self) -> SignalContext:
        home = Path(self.tmp_path)
        path = MetricsPaths(home).resources()
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(_sample()) + "\n", encoding="utf-8")
        return SignalContext(home, NOW, app_names=["demo-api"])

    def test_cpu(self) -> None:
        source = ResourcesMetricSource()
        ctx = self._ctx()
        series = source.query(
            {"target": "demo-api", "metric": "cpu_percent"},
            window_seconds=300,
            ctx=ctx,
        )
        assert series[0].points[0].value == 90.0
        star = source.query(
            {"target": "*", "metric": "cpu_percent"}, window_seconds=300, ctx=ctx
        )
        assert any(s.subject == "demo-api" for s in star)
