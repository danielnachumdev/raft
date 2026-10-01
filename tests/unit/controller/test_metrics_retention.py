"""Metrics JSONL retention: age + size, oldest first."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from raft.controller.metrics_retention import MetricsRetention


class TestMetricsRetention:
    def _write(self, path: Path, rows: list) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
            encoding="utf-8",
        )

    def test_drops_old_lines_by_age(self, tmp_path: Path) -> None:
        path = tmp_path / "resources.jsonl"
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        self._write(
            path,
            [
                {"ts": (now - timedelta(days=40)).isoformat(), "n": 1},
                {"ts": (now - timedelta(days=1)).isoformat(), "n": 2},
            ],
        )
        MetricsRetention(max_age_days=30, max_bytes=10_000_000, wall_clock=lambda: now).prune(
            path
        )
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert [row["n"] for row in rows] == [2]

    def test_trims_oldest_when_over_max_bytes(self, tmp_path: Path) -> None:
        path = tmp_path / "resources.jsonl"
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        # Each line ~20+ bytes; tiny max_bytes forces dropping the first.
        self._write(
            path,
            [
                {"ts": now.isoformat(), "n": 1, "pad": "xxxx"},
                {"ts": now.isoformat(), "n": 2, "pad": "xxxx"},
                {"ts": now.isoformat(), "n": 3, "pad": "xxxx"},
            ],
        )
        MetricsRetention(max_age_days=30, max_bytes=80, wall_clock=lambda: now).prune(path)
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert rows
        assert rows[0]["n"] > 1
        assert path.stat().st_size <= 80

    def test_noop_when_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.jsonl"
        MetricsRetention(max_age_days=30, max_bytes=100).prune(path)
        assert not path.exists()

    def test_invalid_or_missing_ts_treated_as_ancient(self, tmp_path: Path) -> None:
        path = tmp_path / "resources.jsonl"
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        path.write_text(
            "\nnot-json\n"
            + json.dumps({"ts": "fixed", "n": 1})
            + "\n"
            + json.dumps({"n": 2})
            + "\n"
            + json.dumps({"ts": now.isoformat(), "n": 3})
            + "\n"
            + json.dumps({"ts": "2026-06-01T00:00:00", "n": 4})
            + "\n",
            encoding="utf-8",
        )
        MetricsRetention(max_age_days=30, max_bytes=10_000_000, wall_clock=lambda: now).prune(
            path
        )
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert [row["n"] for row in rows] == [3, 4]

    def test_skips_when_max_bytes_non_positive(self, tmp_path: Path) -> None:
        path = tmp_path / "resources.jsonl"
        path.write_text('{"ts":"2026-06-01T00:00:00Z","n":1}\n', encoding="utf-8")
        MetricsRetention(max_age_days=30, max_bytes=0).prune(path)
        assert path.read_text(encoding="utf-8").startswith("{")
