"""Unit tests for GraphEvent + GraphEventStore."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from raft.models.graph_event import GraphEvent
from raft.models.graph_event_store import (
    KIND_DEPLOYMENT,
    KIND_SCALING,
    KIND_STOP,
    SCALING_ACTION_IDLE_STOP,
    SCALING_ACTION_WAKE,
    GraphEventStore,
)

from ..base import RaftTestCase


class TestGraphEvent(RaftTestCase):
    def test_round_trip_mapping(self) -> None:
        event = GraphEvent(
            kind=KIND_DEPLOYMENT,
            ts="2026-10-03T12:00:00+00:00",
            service="demo-web",
            label="Deploy web",
            metadata={"app": "web", "ref": "abc"},
            id="e1",
        )
        got = GraphEvent.from_mapping(event.to_mapping())
        assert got == event

    def test_minimal_mapping_omits_empty_optionals(self) -> None:
        event = GraphEvent(kind="note", ts="2026-10-03T12:00:00Z")
        assert event.to_mapping() == {"kind": "note", "ts": "2026-10-03T12:00:00Z"}
        got = GraphEvent.from_mapping({"kind": " note ", "ts": " t ", "metadata": 1})
        assert got is not None
        assert got.metadata == {}

    def test_from_mapping_rejects_bad_rows(self) -> None:
        assert GraphEvent.from_mapping({}) is None
        assert GraphEvent.from_mapping({"kind": "x"}) is None
        assert GraphEvent.from_mapping({"ts": "t"}) is None


class TestGraphEventStore(RaftTestCase):
    def test_record_deployment_appends_readable_event(self) -> None:
        home = self.tmp_path / "raft"
        store = GraphEventStore(home)
        when = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        stored = store.record_deployment(
            service="demo-web",
            app="web",
            ref="deadbeef",
            ts=when,
        )
        assert stored.kind == KIND_DEPLOYMENT
        assert stored.id
        assert stored.service == "demo-web"
        rows = store.events_in_window(from_ts=when - timedelta(minutes=1))
        assert len(rows) == 1
        assert rows[0].metadata["ref"] == "deadbeef"
        self._assert_jsonl_line(home, stored.id)

    def _assert_jsonl_line(self, home: Path, event_id: str) -> None:
        path = home / "state" / "events" / "graph.jsonl"
        payload = json.loads(path.read_text(encoding="utf-8").strip())
        assert payload["id"] == event_id
        assert payload["kind"] == KIND_DEPLOYMENT

    def test_events_in_window_filters_time_and_service(self) -> None:
        home = self.tmp_path / "raft"
        store = GraphEventStore(home)
        now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        store.record_deployment(
            service="a", app="a", ref="1", ts=now - timedelta(hours=2)
        )
        store.record_deployment(
            service="b", app="b", ref="2", ts=now - timedelta(minutes=5)
        )
        store.record_deployment(
            service="a", app="a", ref="3", ts=now - timedelta(minutes=1)
        )
        got = store.events_in_window(
            from_ts=now - timedelta(hours=1),
            to_ts=now,
            services=["a"],
        )
        assert [e.metadata["ref"] for e in got] == ["3"]

    def test_skips_corrupt_lines_and_missing_file(self) -> None:
        home = self.tmp_path / "raft"
        store = GraphEventStore(home)
        assert store.events_in_window(from_ts=datetime.now(timezone.utc)) == []
        path = home / "state" / "events" / "graph.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text(
            "\nnot-json\n{\"kind\":\"x\"}\n[]\n"
            '{"kind":"deployment","ts":"not-a-ts"}\n',
            encoding="utf-8",
        )
        assert (
            store.events_in_window(from_ts=datetime(2020, 1, 1, tzinfo=timezone.utc))
            == []
        )

    def test_global_event_passes_service_filter(self) -> None:
        home = self.tmp_path / "raft"
        store = GraphEventStore(home)
        when = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        store.append(
            GraphEvent(kind="note", ts=when.isoformat(), label="global")
        )
        got = store.events_in_window(from_ts=when, services=["demo-web"])
        assert len(got) == 1
        assert got[0].service is None

    def test_naive_ts_treated_as_utc(self) -> None:
        home = self.tmp_path / "raft"
        store = GraphEventStore(home)
        store.append(GraphEvent(kind="note", ts="2026-10-03T12:00:00"))
        got = store.events_in_window(
            from_ts=datetime(2026, 10, 3, 11, 0, tzinfo=timezone.utc),
            to_ts=datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc),
        )
        assert len(got) == 1

    def test_to_ts_excludes_later_events(self) -> None:
        home = self.tmp_path / "raft"
        store = GraphEventStore(home)
        when = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        store.append(GraphEvent(kind="note", ts=when.isoformat(), id="keep"))
        later = store.events_in_window(
            from_ts=when - timedelta(hours=1),
            to_ts=when - timedelta(minutes=1),
        )
        assert later == []
        kept = store.events_in_window(from_ts=when - timedelta(hours=1), to_ts=when)
        assert [e.id for e in kept] == ["keep"]

    def test_record_stop(self) -> None:
        home = self.tmp_path / "raft"
        store = GraphEventStore(home)
        when = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        stop = store.record_stop(service="demo-web", app="web", ts=when)
        edge = store.record_stop(service="raft-gate", ts=when)
        assert stop.kind == KIND_STOP
        assert stop.label == "Stop web"
        assert stop.metadata["app"] == "web"
        assert edge.metadata == {}
        assert edge.label == "Stop raft-gate"

    def test_record_scaling_idle_and_wake(self) -> None:
        home = self.tmp_path / "raft"
        store = GraphEventStore(home)
        when = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        idle = store.record_scaling(
            service="demo-web",
            app="web",
            action=SCALING_ACTION_IDLE_STOP,
            ts=when,
        )
        wake = store.record_scaling(
            service="demo-web",
            app="web",
            action=SCALING_ACTION_WAKE,
            ts=when,
        )
        assert idle.kind == KIND_SCALING
        assert idle.metadata["action"] == SCALING_ACTION_IDLE_STOP
        assert idle.label == "Idle stop web"
        assert wake.label == "Wake web"

    def test_record_scaling_unknown_action_label(self) -> None:
        home = self.tmp_path / "raft"
        when = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        other = GraphEventStore(home).record_scaling(
            service="x", app="x", action="other", ts=when
        )
        assert other.label == "Scale x"
