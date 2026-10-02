"""Edge-case coverage for metrics JSONL / series builders."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

from raft.controller.metrics import METRICS_DIR, METRICS_FILENAME
from raft.services.read.metrics import MetricsRead
from raft.services.read.metrics_jsonl import MetricsJsonlReader
from raft.services.read.metrics_series import MetricsSeriesBuilder
from raft.services.serve.page import ServePage

from ...base import RaftTestCase


class TestMetricsEdges(RaftTestCase):
    def test_clamp_window_and_naive_ts(self) -> None:
        assert MetricsRead._clamp_window(0) == 3600
        assert MetricsRead._clamp_window(120) == 120
        assert MetricsRead._clamp_window(999999) == 604800
        naive = MetricsJsonlReader.parse_ts("2026-10-02T12:00:00")
        assert naive is not None and naive.tzinfo is not None
        assert MetricsJsonlReader.parse_ts("") is None
        assert MetricsJsonlReader.parse_ts("nope") is None
        assert MetricsJsonlReader._parse_line("[1]") is None

    def test_reverse_read_without_trailing_newline(self) -> None:
        home = self.tmp_path / "raft"
        path = home / METRICS_DIR / METRICS_FILENAME
        path.parent.mkdir(parents=True)
        now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        row = {"ts": now.isoformat(), "host": {"cpus": 1}, "containers": []}
        path.write_bytes(json.dumps(row).encode("utf-8"))  # no trailing \n
        got = MetricsJsonlReader(path).samples_in_window(
            from_ts=now - timedelta(hours=1)
        )
        assert len(got) == 1

    def test_series_skips_malformed_rows(self) -> None:
        builder = MetricsSeriesBuilder()
        samples: list[Dict[str, Any]] = [
            {"ts": 1},
            {"ts": "t0", "host": "x", "containers": "nope"},
            {
                "ts": "t1",
                "host": {"loadavg": ["bad"], "cpus": 2},
                "containers": [
                    None,
                    {"service": 7},
                    {"service": ""},
                    {"service": "other"},
                ],
            },
            {"ts": "t2", "host": {}, "containers": [{"service": "app"}]},
        ]
        series = builder.build(samples, wanted={"host", "app"})
        assert series["host"]["points"][0]["cpu_percent"] is None
        assert "app" in series
        assert {a["id"] for a in builder.available(samples)} >= {"host", "app"}

    def test_container_point_coerces_string_metrics(self) -> None:
        point = MetricsSeriesBuilder._container_point(
            self._full_runtime_row(), ts="t"
        )
        expected = {
            "cpu_percent": 1.5,
            "memory_used_percent": 20.0,
            "memory_used_bytes": 512.0,
            "memory_limit_bytes": 1024.0,
            "uptime_seconds": 90.0,
            "pids": 3.0,
            "network_rx_bytes": 10.0,
            "network_tx_bytes": 20.0,
            "block_read_bytes": 30.0,
            "block_write_bytes": 40.0,
        }
        assert {k: point[k] for k in expected} == expected

    def test_container_point_missing_nested_io_is_null(self) -> None:
        point = MetricsSeriesBuilder._container_point(
            {"service": "app", "cpu_percent": 1.0, "memory": "bad"},
            ts="t",
        )
        assert point["memory_used_percent"] is None
        assert point["network_rx_bytes"] is None
        assert point["block_write_bytes"] is None

    @staticmethod
    def _full_runtime_row() -> Dict[str, Any]:
        return {
            "service": "raft-gate",
            "cpu_percent": "1.5",
            "uptime_seconds": "90",
            "pids": "3",
            "memory": {
                "used_percent": "20.0",
                "used_bytes": "512",
                "limit_bytes": "1024",
            },
            "network": {"rx_bytes": "10", "tx_bytes": "20"},
            "block_io": {"read_bytes": "30", "write_bytes": "40"},
        }

    def test_as_float_rejects_bool_nan_and_junk(self) -> None:
        assert MetricsSeriesBuilder._as_float(True) is None
        assert MetricsSeriesBuilder._as_float("nope") is None
        assert MetricsSeriesBuilder._as_float(float("nan")) is None
        assert MetricsSeriesBuilder._as_float({}) is None

    def test_empty_jsonl_file(self) -> None:
        home = self.tmp_path / "raft"
        path = home / METRICS_DIR / METRICS_FILENAME
        path.parent.mkdir(parents=True)
        path.write_text("", encoding="utf-8")
        assert MetricsJsonlReader(path).samples_in_window(
            from_ts=datetime(2026, 1, 1, tzinfo=timezone.utc)
        ) == []

    def test_host_cpu_load_without_cpus(self) -> None:
        point = MetricsSeriesBuilder._host_point(
            {"loadavg": [1.5], "memory": {}}, ts="t"
        )
        assert point["cpu_percent"] == 1.5
        assert MetricsSeriesBuilder._host_cpu_percent({"loadavg": []}) is None

    def test_split_services_empty_tokens(self) -> None:
        assert ServePage._split_services(None) is None
        assert ServePage._split_services("  ") is None
        assert ServePage._split_services(" , , ") is None
        assert ServePage._split_services("a, b") == ["a", "b"]

    def test_wanted_skips_host(self) -> None:
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
        path = home / METRICS_DIR / METRICS_FILENAME
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "ts": now.isoformat(),
                    "host": {"cpus": 2, "loadavg": [1.0], "memory": {}},
                    "containers": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        payload = MetricsRead(home).history(
            window_seconds=3600, services=["missing"], now=now
        )
        assert payload["series"] == []
