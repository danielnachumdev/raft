"""GraphEventsSource query paths."""

from datetime import datetime, timezone, timedelta
from pathlib import Path

from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.alerts.signals.control.graph_events_source import GraphEventsSource
from tests.unit.base import RaftTestCase


class TestGraphEventsSource(RaftTestCase):
    def test_query_targets(self) -> None:
        home = Path(self.tmp_path)
        store = GraphEventStore(home)
        now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        store.record_deployment(service="demo-api", app="demo-api", ref="abc", ts=now)
        ctx = SignalContext(home, now, app_names=["demo-api"])
        src = GraphEventsSource()
        issues = src.validate_select({"target": "demo-api", "eventKind": "deployment"}, path="s")
        assert issues == []
        series = src.query({"target": "demo-api", "eventKind": "deployment"}, window_seconds=3600, ctx=ctx)
        assert series[0].points
        dash = src.query({"target": "-", "eventKind": "deployment"}, window_seconds=3600, ctx=ctx)
        assert dash
