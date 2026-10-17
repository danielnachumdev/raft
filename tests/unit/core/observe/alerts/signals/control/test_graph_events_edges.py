"""GraphEventsSource edge targets."""
from datetime import datetime, timezone
from pathlib import Path
from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.observe.alerts.signals.context import SignalContext
from raft.core.observe.alerts.signals.control.graph_events_source import GraphEventsSource
from tests.unit.base import RaftTestCase

class TestGraphEventsEdges(RaftTestCase):
    def test_wildcard_and_validate(self) -> None:
        home = Path(self.tmp_path)
        store = GraphEventStore(home)
        now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        store.record_deployment(service="demo-api", app="demo-api", ref="1", ts=now)
        store.record_deployment(service=None, app=None, ref="2", ts=now)
        src = GraphEventsSource()
        assert src.value_type.value == "event"
        bad = src.validate_select({"target": "demo-api"}, path="s")
        assert bad
        ctx = SignalContext(home, now, app_names=["demo-api"])
        star = src.query({"target": "*", "eventKind": "deployment"}, window_seconds=3600, ctx=ctx)
        assert len(star) >= 1
        filtered = src.query(
            {"target": "demo-api", "eventKind": "deployment", "action": "x"},
            window_seconds=3600,
            ctx=ctx,
        )
        assert filtered
