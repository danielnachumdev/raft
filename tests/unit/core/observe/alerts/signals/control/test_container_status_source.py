"""ContainerStatusSource query paths."""

import json
from datetime import datetime, timezone
from pathlib import Path

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.alerts.signals.control.container_status_source import ContainerStatusSource
from tests.unit.base import RaftTestCase

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


class TestContainerStatusSource(RaftTestCase):
    def test_wildcard_and_scaled_zero(self) -> None:
        home = Path(self.tmp_path)
        path = MetricsPaths(home).resources()
        path.parent.mkdir(parents=True, exist_ok=True)
        sample = {
            "ts": NOW.isoformat(),
            "containers": [{"service": "demo-api", "status": "running"}],
        }
        path.write_text(json.dumps(sample) + "\n", encoding="utf-8")
        ctx = SignalContext(home, NOW, app_names=["demo-api", "demo-web"])
        src = ContainerStatusSource()
        star = src.query({"target": "*"}, window_seconds=300, ctx=ctx)
        assert any(s.subject == "demo-api" for s in star)
        ScalingStore(home).mark_scaled_to_zero("demo-web")
        assert src.query({"target": "demo-web"}, window_seconds=300, ctx=ctx) == []
