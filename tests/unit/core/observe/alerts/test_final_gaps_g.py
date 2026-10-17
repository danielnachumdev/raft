"""Final coverage gaps G: sources + dedupe."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.core.observe.alerts.engine.condition_evaluator import ConditionEvaluator
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.alerts.signals.control.container_status_source import (
    ContainerStatusSource,
)
from raft.core.observe.alerts.signals.control.graph_events_source import (
    GraphEventsSource,
)
from raft.core.observe.alerts.signals.metrics.http_source import HttpMetricSource
from raft.core.observe.alerts.signals.metrics.resources_source import (
    ResourcesMetricSource,
)
from tests.unit.base import RaftTestCase

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


class TestFinalGapsG(RaftTestCase):
    def test_dedupe_http_resources(self) -> None:
        assert ConditionEvaluator._dedupe_subjects(["a", "a", "b"]) == ["a", "b"]
        res = ResourcesMetricSource()
        assert res.describe({"target": "demo-api", "metric": "cpu_percent"})
        assert res._scope("host") == "host"
        assert res._scope("*") == "service"
        assert res._ts(1) is None
        assert res._series_for({}, target="demo-api", metric="cpu_percent")
        built = {"demo-api": {"role": "app", "points": [{"t": 1}]}}
        assert res._series_for(built, target="*", metric="cpu_percent")
        http = HttpMetricSource()
        assert http.validate_select(
            {"target": "*", "metric": "error_rate_5xx"}, path="p"
        ) == []
        assert http._one("demo-api", {"points": [{"t": 1}]}, "requests", wildcard=False)
        assert http._value({"requests": 1, "status_5xx": "x"}, "error_rate_5xx") is None
        assert http._value({"requests": 0, "status_5xx": 1}, "error_rate_5xx") is None

    def test_control_sources(self) -> None:
        cs = ContainerStatusSource()
        assert cs.describe({"target": "demo-api"}) == "demo-api status"
        assert cs._status({"containers": "bad"}, "demo-api") is None
        assert cs._status({"containers": [{"service": "demo-api"}]}, "demo-api") is None
        assert cs._ts("not-an-iso") is None
        home = Path(self.tmp_path)
        ctx = SignalContext(home, NOW, app_names=["demo-api"])
        with patch.object(cs._cache, "samples", return_value=[{"ts": 1}]):
            with patch(
                "raft.core.observe.alerts.signals.control.container_status_source.ScalingStore"
            ) as Store:
                Store.return_value.is_scaled_to_zero.return_value = True
                assert cs.query({"target": "demo-api"}, window_seconds=60, ctx=ctx) == []
                assert cs.query({"target": "*"}, window_seconds=60, ctx=ctx) == []
        ge = GraphEventsSource()
        assert ge.describe({"target": "demo-api", "eventKind": "restart"})
        assert ge._point(MagicMock(ts="bad"), "restart") is None
