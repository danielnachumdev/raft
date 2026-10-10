"""Unit tests for HttpMetricsRead + series shaping."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from raft.config.settings_types import MetricsConfig
from raft.controller.http_metrics import HTTP_METRICS_FILENAME
from raft.controller.metrics import METRICS_DIR
from raft.read.http_metrics import HttpMetricsRead
from raft.read.http_metrics_series import HttpMetricsSeriesBuilder

from tests.unit.base import RaftTestCase

_NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)


def _row(ts: str, **extra: Any) -> Dict[str, Any]:
    base = {
        "ts": ts,
        "requests": 10,
        "rps": 0.1667,
        "in_flight": 2,
        "active_connections": 5,
        "duration_ms": {"avg": 12.0, "p50": 10.0, "p95": 20.0, "p99": 30.0},
        "status_class": {"2xx": 9, "3xx": 0, "4xx": 1, "5xx": 0, "other": 0},
        "by_service": {
            "demo-api": {
                "requests": 10,
                "rps": 0.1667,
                "duration_ms": {"avg": 12.0, "p50": 10.0, "p95": 20.0, "p99": 30.0},
                "status_class": {"2xx": 9, "3xx": 0, "4xx": 1, "5xx": 0, "other": 0},
            }
        },
    }
    base.update(extra)
    return base


class TestHttpMetricsRead(RaftTestCase):
    def _write(self, home: Path, rows: List[Dict[str, Any]]) -> None:
        path = home / METRICS_DIR / HTTP_METRICS_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def test_history_builds_edge_and_service_series(self) -> None:
        ts = (_NOW - timedelta(minutes=1)).isoformat()
        self._write(self.tmp_path, [_row(ts)])
        payload = HttpMetricsRead(self.tmp_path).history(window_seconds=3600, now=_NOW)
        assert payload["kind"] == "http"
        ids = {s["id"] for s in payload["series"]}
        assert ids == {"edge", "demo-api"}
        edge = next(s for s in payload["series"] if s["id"] == "edge")
        assert edge["points"][0]["duration_p95_ms"] == 20.0
        assert edge["points"][0]["status_4xx"] == 1

    def test_services_filter(self) -> None:
        ts = (_NOW - timedelta(minutes=1)).isoformat()
        self._write(self.tmp_path, [_row(ts)])
        payload = HttpMetricsRead(self.tmp_path).history(
            window_seconds=3600, now=_NOW, services=["demo-api"]
        )
        assert [s["id"] for s in payload["series"]] == ["demo-api"]

    def test_clamp_message_and_downsample(self) -> None:
        rows = [
            _row((_NOW - timedelta(minutes=5 - i)).isoformat(), requests=i, rps=float(i))
            for i in range(5)
        ]
        self._write(self.tmp_path, rows)
        payload = HttpMetricsRead(self.tmp_path).history(
            window_seconds=3600, now=_NOW, max_points=2
        )
        edge = next(s for s in payload["series"] if s["id"] == "edge")
        assert len(edge["points"]) == 2

    def test_skips_bad_samples_and_filters(self) -> None:
        builder = HttpMetricsSeriesBuilder()
        out = builder.build(_messy_samples(), wanted={"edge", "keep"})
        assert "edge" in out and "keep" in out and "skip" not in out
        bare = builder.build(
            [{"ts": "2026-10-09T12:00:00+00:00", "by_service": {"x": "bad"}}],
            wanted=None,
        )
        assert "x" not in bare
        avail = builder.available(
            [
                {"ts": "t", "by_service": None},
                {"ts": "t", "by_service": {1: {}, "a": {}}},
            ]
        )
        assert any(a["id"] == "a" for a in avail)
        assert builder._as_float([]) is None
        assert builder.downsample({"points": [1, 2, 3]}, max_points=0)["points"] == [1, 2, 3]

    def test_history_includes_clamp_message(self) -> None:
        self._write(self.tmp_path, [_row((_NOW - timedelta(days=40)).isoformat())])
        reader = HttpMetricsRead(
            self.tmp_path, metrics_config=MetricsConfig(retention_max_age_days=7)
        )
        payload = reader.history(window_seconds=86400 * 30, now=_NOW)
        assert payload.get("clamped") is True
        assert payload.get("clamp_message")


def _messy_samples() -> List[Dict[str, Any]]:
    return [
        {"ts": None},
        {"ts": "2026-10-09T12:00:00+00:00", "by_service": "not-a-dict"},
        {
            "ts": "2026-10-09T12:00:00+00:00",
            "by_service": {
                "": {"requests": 1},
                "demo-api": "bad",
                "skip": _svc_window(),
                "keep": _svc_window(avg=float("nan")),
            },
        },
    ]


def _svc_window(*, avg: float = 1.0) -> Dict[str, Any]:
    return {
        "requests": 1,
        "rps": 1.0,
        "duration_ms": {"avg": avg, "p50": 1, "p95": 1, "p99": 1},
        "status_class": {"2xx": 1, "3xx": 0, "4xx": 0, "5xx": 0, "other": 0},
    }
