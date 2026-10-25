"""StatusResourcesOverlay from controller resources.jsonl."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from raft.core.core.config.paths.metrics_paths import MetricsPaths
from raft.core.core.models.app import EDGE_GROUP
from raft.core.observe.ops.status.models import StatusSnapshot
from raft.core.observe.read.status_resources_overlay import StatusResourcesOverlay

from tests.unit.base import RaftTestCase
from tests.unit.core.observe.ops.status import fixtures as status_fx


class TestStatusResourcesOverlay(RaftTestCase):
    def test_overlays_cpu_mem_from_fresh_sample(self) -> None:
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self._write_sample(self.tmp_path, ts=(now - timedelta(seconds=30)).isoformat())
        overlay = StatusResourcesOverlay(self.tmp_path, now=now)
        out = overlay.apply(self._lite_gate())
        self._assert_full_overlay(out.containers[0], overlay)

    def test_stale_sample_leaves_live_rows(self) -> None:
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self._write_sample(
            self.tmp_path, ts=(now - timedelta(seconds=500)).isoformat()
        )
        overlay = StatusResourcesOverlay(self.tmp_path, now=now)
        out = overlay.apply(self._lite_gate())
        assert out.containers[0].cpu_percent is None
        assert overlay.resources_as_of is None

    def test_missing_jsonl_is_noop(self) -> None:
        overlay = StatusResourcesOverlay(self.tmp_path)
        assert overlay.apply(self._lite_gate()).containers[0].cpu_percent is None
        assert overlay.resources_as_of is None

    def test_bad_container_rows_ignored(self) -> None:
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self._write_raw(
            self.tmp_path,
            {
                "ts": now.isoformat(),
                "containers": [None, {"service": ""}, "x", {"service": "other"}],
            },
        )
        out = StatusResourcesOverlay(self.tmp_path, now=now).apply(self._lite_gate())
        assert out.containers[0].cpu_percent is None

    def test_invalid_numeric_fields_keep_fallback(self) -> None:
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self._write_raw(self.tmp_path, self._bad_numeric_sample(now))
        live = status_fx.snapshot(
            status_fx.container(
                "raft-gate", role="gate", group=EDGE_GROUP, cpu=1.0, pids=3
            )
        )
        out = StatusResourcesOverlay(self.tmp_path, now=now).apply(live)
        assert out.containers[0].cpu_percent == 1.0
        assert out.containers[0].pids == 3

    def test_empty_containers_list_is_noop(self) -> None:
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self._write_raw(self.tmp_path, {"ts": now.isoformat(), "containers": []})
        overlay = StatusResourcesOverlay(self.tmp_path, now=now)
        out = overlay.apply(self._lite_gate())
        assert out.containers[0].cpu_percent is None
        assert overlay.resources_as_of is None

    def test_non_list_containers_and_blank_ts_label(self) -> None:
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self._write_raw(self.tmp_path, {"ts": now.isoformat(), "containers": {}})
        out = StatusResourcesOverlay(self.tmp_path, now=now).apply(self._lite_gate())
        assert out.containers[0].cpu_percent is None
        assert StatusResourcesOverlay._ts_label({"ts": "  "}) is None
        assert StatusResourcesOverlay._ts_label({"ts": 1}) is None

    def test_partial_memory_and_bad_network_keep_fallback(self) -> None:
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self._write_raw(self.tmp_path, self._partial_bad_io_sample(now))
        live = status_fx.snapshot(
            status_fx.container(
                "raft-gate", role="gate", group=EDGE_GROUP, cpu=2.0, mem_pct=5.0
            )
        )
        out = StatusResourcesOverlay(self.tmp_path, now=now).apply(live)
        assert out.containers[0].cpu_percent == 2.0
        assert out.containers[0].memory.used_percent == 5.0

    def test_future_sample_is_stale(self) -> None:
        now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self._write_sample(
            self.tmp_path, ts=(now + timedelta(seconds=30)).isoformat()
        )
        out = StatusResourcesOverlay(self.tmp_path, now=now).apply(self._lite_gate())
        assert out.containers[0].cpu_percent is None

    @staticmethod
    def _lite_gate() -> StatusSnapshot:
        return status_fx.snapshot(
            status_fx.container(
                "raft-gate",
                role="gate",
                group=EDGE_GROUP,
                cpu=None,
                mem_used=None,
                mem_limit=None,
                mem_pct=None,
                pids=None,
            )
        )

    @staticmethod
    def _assert_full_overlay(row, overlay: StatusResourcesOverlay) -> None:
        assert row.cpu_percent == 12.5
        assert row.memory.used_percent == 40.0
        assert row.memory.used_bytes == 1024
        assert row.memory.limit_bytes == 2048
        assert row.pids == 7
        assert row.network.rx_or_read_bytes == 10
        assert row.block_io.tx_or_write_bytes == 4
        assert overlay.resources_as_of is not None

    @staticmethod
    def _bad_numeric_sample(now: datetime) -> Dict[str, Any]:
        return {
            "ts": now.isoformat(),
            "containers": [
                {
                    "service": "raft-gate",
                    "cpu_percent": "nope",
                    "memory": "bad",
                    "network": {"rx_bytes": "x"},
                    "block_io": 1,
                    "pids": "z",
                }
            ],
        }

    @staticmethod
    def _partial_bad_io_sample(now: datetime) -> Dict[str, Any]:
        return {
            "ts": now.isoformat(),
            "containers": [
                {
                    "service": "raft-gate",
                    "cpu_percent": None,
                    "memory": {},
                    "network": "bad",
                    "block_io": "bad",
                }
            ],
        }

    @staticmethod
    def _write_sample(home: Path, *, ts: str) -> None:
        TestStatusResourcesOverlay._write_raw(
            home,
            {
                "ts": ts,
                "containers": [
                    {
                        "service": "raft-gate",
                        "cpu_percent": 12.5,
                        "memory": {
                            "used_bytes": 1024,
                            "limit_bytes": 2048,
                            "used_percent": 40.0,
                        },
                        "network": {"rx_bytes": 10, "tx_bytes": 20},
                        "block_io": {"read_bytes": 3, "write_bytes": 4},
                        "pids": 7,
                    }
                ],
            },
        )

    @staticmethod
    def _write_raw(home: Path, row: Dict[str, Any]) -> None:
        path = MetricsPaths(home).resources()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
