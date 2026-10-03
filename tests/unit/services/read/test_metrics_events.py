"""MetricsRead includes GraphEvents from state/events/graph.jsonl."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from raft.models.graph_event_store import (
    KIND_SCALING,
    KIND_STOP,
    SCALING_ACTION_IDLE_STOP,
    GraphEventStore,
)
from raft.services.read.metrics import MetricsRead

from .test_metrics_read import _MetricsFixtures
from ...base import RaftTestCase


class TestMetricsReadEvents(RaftTestCase):
    def test_history_includes_window_events(self) -> None:
        home, now = self._seed_samples()
        self._record(home, "raft-gate", "abc", now - timedelta(minutes=3))
        self._record(home, "other", "zzz", now - timedelta(minutes=2))
        payload = MetricsRead(home).history(
            window_seconds=3600, services=["raft-gate"], now=now
        )
        assert [e["metadata"]["ref"] for e in payload["events"]] == ["abc"]

    def test_history_events_ignore_since_cursor(self) -> None:
        home, now = self._seed_samples()
        mid = now - timedelta(minutes=10)
        self._record(home, "raft-gate", "old", mid)
        payload = MetricsRead(home).history(
            window_seconds=3600, since=mid.isoformat(), now=now
        )
        assert len(payload["events"]) == 1
        assert payload["events"][0]["metadata"]["ref"] == "old"

    def test_history_includes_stop_and_scaling_events(self) -> None:
        home, now = self._seed_samples()
        store = GraphEventStore(home)
        store.record_stop(
            service="web", app="web", ts=now - timedelta(minutes=4)
        )
        store.record_scaling(
            service="web",
            app="web",
            action=SCALING_ACTION_IDLE_STOP,
            ts=now - timedelta(minutes=2),
        )
        payload = MetricsRead(home).history(
            window_seconds=3600, services=["web"], now=now
        )
        kinds = [e["kind"] for e in payload["events"]]
        assert kinds == [KIND_STOP, KIND_SCALING]

    def test_history_empty_events_when_no_store(self) -> None:
        home = self.tmp_path / "raft"
        payload = MetricsRead(home).history(now=datetime.now(timezone.utc))
        assert payload["events"] == []

    def _seed_samples(self):
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        _MetricsFixtures.write_jsonl(
            home, [_MetricsFixtures.sample(now - timedelta(minutes=5))]
        )
        return home, now

    @staticmethod
    def _record(home, service: str, ref: str, ts: datetime) -> None:
        GraphEventStore(home).record_deployment(
            service=service, app=service, ref=ref, ts=ts
        )
