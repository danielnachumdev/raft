"""HttpMetricSource validate and edge targets."""

import json
from datetime import datetime, timezone
from pathlib import Path

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.alerts.signals.metrics.http_source import HttpMetricSource
from tests.unit.base import RaftTestCase

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


class TestHttpSourceEdges(RaftTestCase):
    def test_validate_and_edge(self) -> None:
        home = Path(self.tmp_path)
        path = MetricsPaths(home).http()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"ts": NOW.isoformat(), "requests": 0, "by_service": {}}) + "\n",
            encoding="utf-8",
        )
        src = HttpMetricSource()
        issues = src.validate_select({"target": "edge", "metric": "requests"}, path="s")
        assert issues == []
        ctx = SignalContext(home, NOW, app_names=[])
        edge = src.query({"target": "edge", "metric": "requests"}, window_seconds=60, ctx=ctx)
        assert edge[0].subject == "edge"
