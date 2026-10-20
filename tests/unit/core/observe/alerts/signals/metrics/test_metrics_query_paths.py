"""HTTP/resources query edge paths."""
import json
from datetime import datetime, timezone
from pathlib import Path

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.alerts.signals.metrics.http_source import HttpMetricSource
from raft.core.observe.alerts.signals.metrics.resources_source import ResourcesMetricSource
from tests.unit.base import RaftTestCase

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


class TestMetricsQueryPaths(RaftTestCase):
    def test_http_wildcard_and_bad_ts(self) -> None:
        home = Path(self.tmp_path)
        path = MetricsPaths(home).http()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "ts": NOW.isoformat(),
                    "requests": 10,
                    "status_5xx": 1,
                    "by_service": {"demo-api": {"requests": 10, "status_5xx": 1, "points": [{"t": "bad"}]}},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        src = HttpMetricSource()
        ctx = SignalContext(home, NOW, app_names=["demo-api"])
        assert src.validate_select({"target": "*", "metric": "requests"}, path="s") == []
        star = src.query({"target": "*", "metric": "requests"}, window_seconds=60, ctx=ctx)
        assert star

    def test_resources_wildcard_missing_host(self) -> None:
        home = Path(self.tmp_path)
        path = MetricsPaths(home).resources()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"ts": NOW.isoformat(), "host": {"memory": {"used_percent": 1}}}) + "\n",
            encoding="utf-8",
        )
        src = ResourcesMetricSource()
        ctx = SignalContext(home, NOW, app_names=["demo-api"])
        issues = src.validate_select({"target": "host", "metric": "memory_limit_bytes"}, path="s")
        assert issues
        missing = src.query({"target": "missing", "metric": "cpu_percent"}, window_seconds=60, ctx=ctx)
        assert missing[0].points == ()
        assert src.describe({"target": "demo-api", "metric": "cpu_percent"})
        star = src.query({"target": "*", "metric": "cpu_percent"}, window_seconds=60, ctx=ctx)
        assert isinstance(star, list)
