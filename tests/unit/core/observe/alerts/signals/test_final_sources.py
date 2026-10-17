"""Final source edge coverage."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

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
from raft.core.observe.alerts.signals.series import ValueType
from tests.unit.base import RaftTestCase

NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


class TestFinalSources(RaftTestCase):
    def test_http_validate_and_ts(self) -> None:
        http = HttpMetricSource()
        assert http.validate_select({}, path="p")
        assert http.validate_select(
            {"target": "demo-api", "metric": "in_flight"}, path="p"
        )
        assert http._ts(1) is None
        assert http._ts("bad") is None
        assert http._value({"requests": 0, "status_5xx": 1}, "error_rate_5xx") is None

    def test_resources_and_control(self) -> None:
        res = ResourcesMetricSource()
        assert res.validate_select({}, path="p")
        assert res.validate_select({"target": "host", "metric": "pids"}, path="p")
        assert res._ts("bad") is None
        cs = ContainerStatusSource()
        assert cs.value_type == ValueType.STATE
        assert any("target" in i.path for i in cs.validate_select({}, path="p"))
        assert cs._ts(1) is None
        ge = GraphEventsSource()
        assert ge.value_type == ValueType.EVENT
        assert ge.validate_select({}, path="p")
        assert ge._parse_ts("bad") is None
