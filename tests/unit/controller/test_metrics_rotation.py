"""Metrics JSONL rotation: seal active; age-delete sealed archives."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from raft.controller.metrics_rotation import MetricsRotation


class TestMetricsRotation:
    def test_seals_oversized_active_without_loading(self, tmp_path: Path) -> None:
        active = tmp_path / "resources.jsonl"
        payload = "x" * 200
        active.write_text(payload, encoding="utf-8")
        now = datetime(2026, 10, 3, 15, 0, 0)
        # Seal day comes from mtime; keep it aligned with the injected clock.
        os.utime(active, (now.timestamp(), now.timestamp()))
        MetricsRotation(max_age_days=30, max_bytes=100, wall_clock=lambda: now).maintain(
            active
        )
        assert not active.exists()
        sealed = tmp_path / "resources.jsonl.2026-10-03"
        assert sealed.read_text(encoding="utf-8") == payload

    def test_deletes_archives_older_than_max_days(self, tmp_path: Path) -> None:
        active = tmp_path / "resources.jsonl"
        keep = tmp_path / "resources.jsonl.2026-05-20"
        drop = tmp_path / "resources.jsonl.2026-04-01"
        for path in (keep, drop):
            path.write_text("x\n", encoding="utf-8")
        now = datetime(2026, 6, 1, 12, 0, 0)
        MetricsRotation(max_age_days=30, max_bytes=10_000_000, wall_clock=lambda: now).maintain(
            active
        )
        assert keep.exists() and not drop.exists()

    def test_noop_when_max_bytes_non_positive(self, tmp_path: Path) -> None:
        active = tmp_path / "resources.jsonl"
        active.write_text("x" * 200, encoding="utf-8")
        MetricsRotation(max_age_days=30, max_bytes=0).maintain(active)
        assert active.exists() and active.stat().st_size == 200

    def test_seals_previous_day_active_by_mtime(self, tmp_path: Path) -> None:
        active = tmp_path / "resources.jsonl"
        active.write_text("yesterday\n", encoding="utf-8")
        stamp = datetime(2026, 10, 2, 18, 0, 0).timestamp()
        os.utime(active, (stamp, stamp))
        now = datetime(2026, 10, 3, 9, 0, 0)
        MetricsRotation(
            max_age_days=30, max_bytes=10_000_000, wall_clock=lambda: now
        ).maintain(active)
        sealed = tmp_path / "resources.jsonl.2026-10-02"
        assert sealed.read_text(encoding="utf-8") == "yesterday\n"

    def test_maintain_when_active_missing_still_cleans_archives(
        self, tmp_path: Path
    ) -> None:
        active = tmp_path / "resources.jsonl"
        drop = tmp_path / "resources.jsonl.2020-01-01"
        drop.write_text("x\n", encoding="utf-8")
        now = datetime(2026, 6, 1, 12, 0, 0)
        MetricsRotation(max_age_days=30, max_bytes=100, wall_clock=lambda: now).maintain(
            active
        )
        assert not drop.exists()
