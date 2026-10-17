"""ContainerStatusSource validate and samples."""
import json
from datetime import datetime, timezone
from pathlib import Path

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.alerts.signals.control.container_status_source import ContainerStatusSource
from tests.unit.base import RaftTestCase

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


class TestContainerQuery(RaftTestCase):
    def test_validate_and_bad_ts(self) -> None:
        home = Path(self.tmp_path)
        path = MetricsPaths(home).resources()
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({"ts": "bad", "containers": [{"service": "demo-api", "status": "running"}]})
            + "\n",
            encoding="utf-8",
        )
        src = ContainerStatusSource()
        assert src.validate_select({}, path="s")
        assert src.value_type.value == "state"
        ctx = SignalContext(home, NOW, app_names=["demo-api"])
        series = src.query({"target": "demo-api"}, window_seconds=300, ctx=ctx)
        assert series[0].points == ()
