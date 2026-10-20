"""ResourcesMetricSource host and validate."""

import json
from datetime import datetime, timezone
from pathlib import Path

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.alerts.signals.metrics.resources_source import ResourcesMetricSource
from tests.unit.base import RaftTestCase

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


class TestResourcesEdges(RaftTestCase):
    def test_host_metric(self) -> None:
        home = Path(self.tmp_path)
        path = MetricsPaths(home).resources()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"ts": NOW.isoformat(), "host": {"cpus": 1, "memory": {"used_percent": 1}}}) + "\n",
            encoding="utf-8",
        )
        src = ResourcesMetricSource()
        issues = src.validate_select({"target": "host", "metric": "memory_used_percent"}, path="s")
        assert issues == []
        ctx = SignalContext(home, NOW, app_names=[])
        series = src.query({"target": "host", "metric": "memory_used_percent"}, window_seconds=60, ctx=ctx)
        assert series[0].subject == "host"
