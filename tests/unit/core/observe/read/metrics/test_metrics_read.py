"""Unit tests for MetricsJsonlReader + MetricsRead history payloads."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from raft.services.controller.jobs.metrics import METRICS_DIR, METRICS_FILENAME
from raft.core.observe.read.metrics import MetricsJsonlReader, MetricsRead

from tests.unit.base import RaftTestCase
from tests.unit.core.observe.read.metrics import fixtures as metrics_fx


class TestMetricsJsonlReader(RaftTestCase):
    def test_samples_in_window_newest_first_filter(self) -> None:
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        path = home / METRICS_DIR / METRICS_FILENAME
        path.parent.mkdir(parents=True)
        lines = [
            json.dumps(metrics_fx.sample(now - timedelta(hours=2), cpu=1)),
            json.dumps(metrics_fx.sample(now - timedelta(minutes=30), cpu=2)),
            json.dumps(metrics_fx.sample(now - timedelta(minutes=5), cpu=3)),
            '{"ts":"bad","host":{},"containers":[]}',
            "not-json",
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        got = MetricsJsonlReader(path).samples_in_window(
            from_ts=now - timedelta(hours=1),
        )
        assert [s["containers"][0]["cpu_percent"] for s in got] == [2, 3]

    def test_since_stops_at_cursor(self) -> None:
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        t1 = now - timedelta(minutes=10)
        t2 = now - timedelta(minutes=5)
        t3 = now - timedelta(minutes=1)
        path = metrics_fx.write_jsonl(
            home,
            [
                metrics_fx.sample(t1, cpu=1),
                metrics_fx.sample(t2, cpu=2),
                metrics_fx.sample(t3, cpu=3),
            ],
        )
        got = MetricsJsonlReader(path).samples_in_window(
            from_ts=now - timedelta(hours=1),
            since=t2,
        )
        assert [s["containers"][0]["cpu_percent"] for s in got] == [3]

    def test_reads_sealed_archives_newest_first(self) -> None:
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        path = home / METRICS_DIR / METRICS_FILENAME
        path.parent.mkdir(parents=True)
        (path.parent / "noise-dir").mkdir()
        archive = path.parent / f"{METRICS_FILENAME}.2026-10-02"
        archive.write_text(
            json.dumps(metrics_fx.sample(now - timedelta(hours=2), cpu=1)) + "\n",
            encoding="utf-8",
        )
        path.write_text(
            json.dumps(metrics_fx.sample(now - timedelta(minutes=5), cpu=9)) + "\n",
            encoding="utf-8",
        )
        got = MetricsJsonlReader(path).samples_in_window(
            from_ts=now - timedelta(hours=3),
        )
        assert [s["containers"][0]["cpu_percent"] for s in got] == [1, 9]

    def test_missing_parent_dir_yields_empty(self) -> None:
        path = self.tmp_path / "missing" / METRICS_FILENAME
        now = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)
        assert (
            MetricsJsonlReader(path).samples_in_window(from_ts=now - timedelta(hours=1))
            == []
        )


class TestMetricsRead(RaftTestCase):
    def test_history_builds_host_and_container_series(self) -> None:
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        metrics_fx.write_jsonl(
            home,
            [
                metrics_fx.sample(now - timedelta(minutes=20), cpu=5.0),
                metrics_fx.sample(now - timedelta(minutes=10), cpu=15.0),
            ],
        )
        payload = MetricsRead(home).history(window_seconds=3600, now=now)
        assert payload["window_seconds"] == 3600
        assert payload["cursor"] is not None
        ids = {s["id"] for s in payload["series"]}
        assert ids == {"host", "raft-gate"}
        gate = next(s for s in payload["series"] if s["id"] == "raft-gate")
        assert gate["label"] == "gate"
        assert [p["cpu_percent"] for p in gate["points"]] == [5.0, 15.0]
        self._assert_runtime_fields(gate["points"][-1])
        host = next(s for s in payload["series"] if s["id"] == "host")
        assert host["points"][0]["cpu_percent"] == 25.0  # 0.5 load / 2 cpus

    @staticmethod
    def _assert_runtime_fields(point: Dict[str, Any]) -> None:
        expected = {
            "memory_limit_bytes": 1000.0,
            "uptime_seconds": 120.0,
            "pids": 4.0,
            "network_rx_bytes": 11.0,
            "network_tx_bytes": 22.0,
            "block_read_bytes": 33.0,
            "block_write_bytes": 44.0,
        }
        assert {k: point[k] for k in expected} == expected

    def test_history_includes_every_container_when_unfiltered(self) -> None:
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        names = ["raft-gate", "raft-router", "demo-web"]
        metrics_fx.write_jsonl(
            home,
            [metrics_fx.multi_sample(now - timedelta(minutes=5), names)],
        )
        payload = MetricsRead(home).history(window_seconds=3600, now=now)
        ids = {s["id"] for s in payload["series"]}
        assert ids == {"host", *names}
        assert {a["id"] for a in payload["available"]} == ids

    def test_history_services_filter_keeps_requested_containers(self) -> None:
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        names = ["raft-gate", "raft-router"]
        metrics_fx.write_jsonl(
            home,
            [metrics_fx.multi_sample(now - timedelta(minutes=5), names)],
        )
        payload = MetricsRead(home).history(
            window_seconds=3600, services=names, now=now
        )
        assert {s["id"] for s in payload["series"]} == set(names)
        assert {a["id"] for a in payload["available"]} >= {"host", *names}

    def test_history_filters_services_and_since(self) -> None:
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        mid = now - timedelta(minutes=10)
        metrics_fx.write_jsonl(
            home,
            [
                metrics_fx.sample(now - timedelta(minutes=20), cpu=1),
                metrics_fx.sample(mid, cpu=2),
                metrics_fx.sample(now - timedelta(minutes=1), cpu=3),
            ],
        )
        payload = MetricsRead(home).history(
            window_seconds=3600,
            since=mid.isoformat(),
            services=["raft-gate"],
            now=now,
        )
        assert [s["id"] for s in payload["series"]] == ["raft-gate"]
        assert len(payload["series"][0]["points"]) == 1
        assert payload["series"][0]["points"][0]["cpu_percent"] == 3

    def test_history_empty_file(self) -> None:
        home = self.tmp_path / "raft"
        payload = MetricsRead(home).history(now=datetime.now(timezone.utc))
        assert payload["series"] == []
        assert payload["available"] == []
        assert payload["cursor"] is None

    def test_downsample_caps_points(self) -> None:
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        rows = [
            metrics_fx.sample(now - timedelta(seconds=i), cpu=float(i))
            for i in range(50, 0, -1)
        ]
        metrics_fx.write_jsonl(home, rows)
        payload = MetricsRead(home).history(
            window_seconds=3600, max_points=10, now=now
        )
        gate = next(s for s in payload["series"] if s["id"] == "raft-gate")
        assert len(gate["points"]) == 10
