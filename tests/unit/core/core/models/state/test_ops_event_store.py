"""Unit tests for OpsEvent + OpsEventStore (append / read / retention)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from raft.core.core.models.state.ops_event import OpsEvent
from raft.core.core.models.state.ops_event_kinds import (
    KIND_DEPLOY_APPLY,
    KIND_STACK_PURGE,
    OpsKindFromGraph,
)
from raft.core.core.models.state.ops_event_store import OpsEventStore
from raft.core.core.models.state.graph_event import GraphEvent
from raft.core.core.models.state.graph_event_kinds import KIND_DEPLOYMENT, KIND_SCALING
from raft.core.core.models.state.graph_event_store import GraphEventStore

from tests.unit.base import RaftTestCase


class TestOpsEvent(RaftTestCase):
    def test_round_trip_mapping(self) -> None:
        event = OpsEvent(
            kind=KIND_DEPLOY_APPLY,
            ts="2026-10-03T12:00:00+00:00",
            summary="Deploy demo-api",
            service="demo-api",
            metadata={"app": "demo-api", "ref": "abc"},
            id="e1",
        )
        assert OpsEvent.from_mapping(event.to_mapping()) == event
        assert event.to_public()["summary"] == "Deploy demo-api"

    def test_from_mapping_rejects_bad_rows(self) -> None:
        assert OpsEvent.from_mapping({}) is None
        assert OpsEvent.from_mapping({"kind": "x"}) is None
        assert OpsEvent.from_mapping({"ts": "t", "kind": "x", "summary": 1}) is not None


class TestOpsKindFromGraph(RaftTestCase):
    def test_maps_deploy_and_scaling(self) -> None:
        apply = GraphEvent(
            kind=KIND_DEPLOYMENT,
            ts="t",
            metadata={"action": "apply"},
        )
        redeploy = GraphEvent(
            kind=KIND_DEPLOYMENT,
            ts="t",
            metadata={"action": "redeploy"},
        )
        wake = GraphEvent(
            kind=KIND_SCALING, ts="t", metadata={"action": "wake"}
        )
        assert OpsKindFromGraph.map(apply) == "deploy.apply"
        assert OpsKindFromGraph.map(redeploy) == "deploy.redeploy"
        assert OpsKindFromGraph.map(wake) == "scale.wake"
        assert OpsKindFromGraph.map(GraphEvent(kind="note", ts="t")) is None


class TestOpsEventStore(RaftTestCase):
    def test_append_and_window_filters(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home)
        now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        self._seed_window_rows(store, now)
        got = store.events_in_window(
            from_ts=now - timedelta(hours=1),
            to_ts=now,
            services=["demo-api"],
            kinds=["deploy.apply"],
        )
        assert [e.summary for e in got] == ["Deploy demo-api"]

    @staticmethod
    def _seed_window_rows(store: OpsEventStore, now: datetime) -> None:
        store.append(
            OpsEvent(
                kind="deploy.apply",
                ts=(now - timedelta(hours=2)).isoformat(),
                summary="old",
                service="demo-api",
            )
        )
        store.record_purge(
            reclaimed_bytes=10, image_bytes=4, builder_bytes=6, ts=now
        )
        store.append(
            OpsEvent(
                kind="deploy.apply",
                ts=(now - timedelta(minutes=1)).isoformat(),
                summary="Deploy demo-api",
                service="demo-api",
            )
        )

    def test_skips_corrupt_and_missing(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home)
        assert store.events_in_window(from_ts=datetime.now(timezone.utc)) == []
        path = home / "host" / "events" / "ops.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\nbad\n{\"kind\":\"x\"}\n[]\n"
            '{"kind":"stack.purge","ts":"not-a-ts","summary":"x"}\n',
            encoding="utf-8",
        )
        assert (
            store.events_in_window(from_ts=datetime(2020, 1, 1, tzinfo=timezone.utc))
            == []
        )

    def test_retention_seals_oversized_active(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home, max_age_days=14, max_bytes=80)
        when = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        for i in range(8):
            store.append(
                OpsEvent(
                    kind=KIND_STACK_PURGE,
                    ts=when.isoformat(),
                    summary=f"purge-{i}-padding-xxxxxxxx",
                )
            )
        parent = home / "host" / "events"
        archives = [
            p for p in parent.iterdir() if p.name.startswith("ops.jsonl.")
        ]
        assert archives, "expected sealed archive after oversize"

    def test_reads_sealed_archives(self) -> None:
        home = self.tmp_path / "raft"
        path = home / "host" / "events" / "ops.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        archive = path.parent / "ops.jsonl.2026-10-02"
        when = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        row = OpsEvent(
            kind="stack.up",
            ts=when.isoformat(),
            summary="Stack up",
            id="arch-1",
        )
        archive.write_text(
            json.dumps(row.to_mapping()) + "\n", encoding="utf-8"
        )
        path.write_text("", encoding="utf-8")
        got = OpsEventStore(home).events_in_window(
            from_ts=when - timedelta(hours=1)
        )
        assert [e.id for e in got] == ["arch-1"]

    def test_graph_dual_write_shares_id(self) -> None:
        home = self.tmp_path / "raft"
        when = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        stored = GraphEventStore(home).record_deployment(
            service="demo-api",
            app="demo-api",
            ref="deadbeef",
            ts=when,
            action="apply",
        )
        ops = OpsEventStore(home).events_in_window(from_ts=when - timedelta(minutes=1))
        assert len(ops) == 1
        assert ops[0].kind == KIND_DEPLOY_APPLY
        assert ops[0].id == stored.id
        assert ops[0].metadata["ref"] == "deadbeef"

    def test_record_helpers_firewall_gate_alert(self) -> None:
        home = self.tmp_path / "raft"
        store = OpsEventStore(home)
        when = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        self._seed_ops_helpers(store, when)
        kinds = [
            e.kind
            for e in store.events_in_window(from_ts=when - timedelta(minutes=1))
        ]
        assert kinds == [
            "firewall.apply",
            "gate.reload",
            "alert.fired",
            "alert.resolved",
        ]

    @staticmethod
    def _seed_ops_helpers(store: OpsEventStore, when: datetime) -> None:
        store.record_firewall_apply(rule_count=3, ts=when)
        store.record_gate_reload(reason="render", ts=when)
        store.record_alert_fired(
            rule_id="demo-api-cpu-high",
            subject="demo-api",
            channel_ids=["ops-webhook"],
            ts=when,
        )
        store.record_alert_resolved(
            rule_id="demo-api-cpu-high", subject="-", ts=when
        )
