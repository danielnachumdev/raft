"""Branch gaps for OpsEvent dual-write, retention edges, and clamps."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.core.core.models.state.graph_event import GraphEvent
from raft.core.core.models.state.ops_event import OpsEvent
from raft.core.core.models.state.ops_event_dual_write import OpsEventDualWrite
from raft.core.core.models.state.ops_event_kinds import OpsKindFromGraph
from raft.core.core.models.state.ops_event_store import OpsEventStore
from raft.core.observe.ops.events import OpsEventsService
from raft.core.observe.ops.events.service import DEFAULT_HOURS, DEFAULT_LIMIT
from raft.services.cli.commands.events import EventsCLI

from tests.unit.base import RaftTestCase


class TestOpsEventGaps(RaftTestCase):
    def test_to_mapping_omits_optional_fields(self) -> None:
        event = OpsEvent(kind="note", ts="2026-10-03T12:00:00Z", summary="x")
        assert "id" not in event.to_mapping()
        assert "service" not in event.to_mapping()
        assert "metadata" not in event.to_mapping()

    def test_scaling_idle_and_unknown(self) -> None:
        idle = GraphEvent(
            kind="scaling", ts="t", metadata={"action": "idle_stop"}
        )
        other = GraphEvent(kind="scaling", ts="t", metadata={"action": "x"})
        assert OpsKindFromGraph.map(idle) == "scale.idle_stop"
        assert OpsKindFromGraph.map(other) is None

    def test_dual_write_skips_unmapped_and_oserror(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home)
        bridge = OpsEventDualWrite(store)
        assert bridge.from_graph(GraphEvent(kind="note", ts="t")) is None
        with patch.object(store, "append", side_effect=OSError("ro")):
            assert (
                bridge.from_graph(
                    GraphEvent(kind="up", ts="2026-10-03T12:00:00+00:00", label="Up")
                )
                is None
            )

    def test_safe_record_oserror(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home)
        with patch.object(store, "_record", side_effect=OSError("ro")):
            assert store.record_purge(
                reclaimed_bytes=0, image_bytes=0, builder_bytes=0
            ) is None

    def test_iter_file_oserror_and_not_file(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home)
        assert list(store._iter_file(home / "missing.jsonl")) == []
        bad = MagicMock(spec=Path)
        bad.is_file.return_value = True
        bad.open.side_effect = OSError("boom")
        assert list(store._iter_file(bad)) == []

    def test_sources_without_active_file(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home)
        parent = home / "host" / "events"
        parent.mkdir(parents=True, exist_ok=True)
        when = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        archive = parent / "ops.jsonl.2026-10-02"
        archive.write_text(
            '{"kind":"stack.up","ts":"%s","summary":"up","id":"a1"}\n'
            % when.isoformat(),
            encoding="utf-8",
        )
        got = store.events_in_window(from_ts=when - timedelta(hours=1))
        assert [e.id for e in got] == ["a1"]


    def test_window_to_ts_and_naive_ts(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home)
        when = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        store.append(
            OpsEvent(kind="note", ts="2026-10-03T12:00:00", summary="naive")
        )
        store.append(
            OpsEvent(kind="note", ts=when.isoformat(), summary="aware", id="a")
        )
        later = store.events_in_window(
            from_ts=when - timedelta(hours=1),
            to_ts=when - timedelta(minutes=1),
        )
        assert later == []
        kept = store.events_in_window(from_ts=when - timedelta(hours=1), to_ts=when)
        assert len(kept) == 2

    def test_archive_entry_skips_non_archive(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home)
        store.ensure_dir()
        junk = store.path.parent / "readme.txt"
        junk.write_text("x", encoding="utf-8")
        from raft.core.core.utils.logging.archive_names import LogArchiveNames

        assert store._archive_entry(LogArchiveNames(store.path), junk) is None

    def test_service_clamps_and_cli_empty(self) -> None:
        assert OpsEventsService._clamp_hours(object()) == DEFAULT_HOURS  # type: ignore[arg-type]
        assert OpsEventsService._clamp_hours(0) == 1
        assert OpsEventsService._clamp_limit(object()) == DEFAULT_LIMIT  # type: ignore[arg-type]
        assert OpsEventsService._clamp_limit(-1) == 1
        stack = MagicMock()
        stack.root = self.tmp_path / "raft"
        EventsCLI(stack)(hours=1, json=False)
