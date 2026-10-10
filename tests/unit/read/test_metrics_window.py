"""Clamp metrics lookback / absolute range against retention."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from raft.controller.metrics import METRICS_DIR, METRICS_FILENAME
from raft.errors.cta import OperatorError
from raft.read.metrics import MetricsRead
from raft.read.metrics_jsonl import MetricsJsonlReader
from raft.read.metrics_window import MetricsRangeQuery

from .test_metrics_read import _MetricsFixtures
from tests.unit.base import RaftTestCase

_NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def _query(
    days: int = 30,
    earliest: Optional[datetime] = None,
    now: datetime = _NOW,
) -> MetricsRangeQuery:
    return MetricsRangeQuery(
        max_age_days=days,
        retention_max_bytes=100,
        earliest=earliest,
        now=now,
    )


class TestMetricsRangeQuery(RaftTestCase):
    def test_relative_presets_and_custom_duration(self) -> None:
        got = _query().resolve(window_seconds=3600)
        assert got.window_seconds == 3600
        assert got.from_ts == _NOW - timedelta(hours=1)
        assert got.to_ts == _NOW
        assert got.clamped is False
        assert _query().resolve(window_seconds=7200).window_seconds == 7200

    def test_relative_clamps_past_retention_days(self) -> None:
        got = _query(days=2).resolve(window_seconds=86400 * 10)
        assert got.window_seconds == 86400 * 2
        assert got.clamped is True
        assert "2 days" in (got.clamp_message or "")

    def test_invalid_window_falls_back_to_default(self) -> None:
        got = _query().resolve(window_seconds=0)
        assert got.window_seconds == 3600
        assert got.clamped is False

    def test_absolute_start_end_and_point_in_time(self) -> None:
        start = _NOW - timedelta(hours=3)
        end = _NOW - timedelta(hours=1)
        got = _query().resolve(
            window_seconds=3600, start=start.isoformat(), end=end.isoformat()
        )
        assert (got.from_ts, got.to_ts, got.window_seconds) == (start, end, 7200)
        pinned = _query().resolve(window_seconds=3600, end=end.isoformat())
        assert pinned.to_ts == end
        assert pinned.from_ts == end - timedelta(hours=1)

    def test_absolute_clamps_before_available_history(self) -> None:
        earliest = _NOW - timedelta(hours=2)
        got = _query(days=7, earliest=earliest).resolve(
            window_seconds=3600,
            start=(_NOW - timedelta(days=5)).isoformat(),
            end=_NOW.isoformat(),
        )
        assert got.from_ts == earliest
        assert got.clamped is True
        assert "7 days" in (got.clamp_message or "")

    def test_future_end_clamps_to_now(self) -> None:
        future = _NOW + timedelta(hours=2)
        got = _query().resolve(
            window_seconds=3600,
            start=(_NOW - timedelta(hours=1)).isoformat(),
            end=future.isoformat(),
        )
        assert got.to_ts == _NOW
        assert got.clamped is True

    def test_bad_iso_raises_operator_error(self) -> None:
        with pytest.raises(OperatorError, match="ISO"):
            _query().resolve(window_seconds=3600, start="not-a-time")

    def test_bounds_expose_retention_and_earliest(self) -> None:
        earliest = _NOW - timedelta(days=1)
        data = _query(days=14, earliest=earliest).bounds().to_mapping()
        assert data["retention_max_age_days"] == 14
        assert data["earliest_ts"] == earliest.isoformat()
        assert data["max_window_seconds"] == 14 * 86400
        assert data["available_from"] == earliest.isoformat()


class TestMetricsReadRange(RaftTestCase):
    def test_history_exposes_bounds_and_absolute_window(self) -> None:
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
        old, mid = now - timedelta(hours=3), now - timedelta(hours=1)
        _MetricsFixtures.write_jsonl(
            home,
            [
                _MetricsFixtures.sample(old, cpu=1),
                _MetricsFixtures.sample(mid, cpu=2),
                _MetricsFixtures.sample(now - timedelta(minutes=1), cpu=3),
            ],
        )
        payload = MetricsRead(home).history(
            window_seconds=3600,
            start=old.isoformat(),
            end=mid.isoformat(),
            now=now,
        )
        gate = next(s for s in payload["series"] if s["id"] == "raft-gate")
        assert [p["cpu_percent"] for p in gate["points"]] == [1, 2]
        assert payload["bounds"]["earliest_ts"] == old.isoformat()

    def test_earliest_ts_and_to_ts_filter(self) -> None:
        home = self.tmp_path / "raft"
        now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
        path = _MetricsFixtures.write_jsonl(
            home,
            [
                _MetricsFixtures.sample(now - timedelta(hours=2), cpu=1),
                _MetricsFixtures.sample(now - timedelta(hours=1), cpu=2),
                _MetricsFixtures.sample(now, cpu=3),
            ],
        )
        reader = MetricsJsonlReader(path)
        assert reader.earliest_ts() == now - timedelta(hours=2)
        got = reader.samples_in_window(
            from_ts=now - timedelta(hours=3),
            to_ts=now - timedelta(minutes=30),
        )
        assert [s["containers"][0]["cpu_percent"] for s in got] == [1, 2]

    def test_history_clamps_window_using_settings(self) -> None:
        home = self.tmp_path / "raft"
        home.mkdir()
        (home / "settings.yaml").write_text(
            "metrics:\n  retentionMaxAgeDays: 2\n", encoding="utf-8"
        )
        now = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
        payload = MetricsRead(home).history(window_seconds=86400 * 10, now=now)
        assert payload["window_seconds"] == 86400 * 2
        assert payload["clamped"] is True
        assert "clamp_message" in payload

    def test_short_window_and_empty_absolute_range(self) -> None:
        got = _query().resolve(window_seconds=30)
        assert got.window_seconds == 60
        assert got.clamped is True
        earliest = _NOW - timedelta(hours=1)
        empty = _query(earliest=earliest).resolve(
            window_seconds=3600,
            start=(_NOW - timedelta(days=2)).isoformat(),
            end=(_NOW - timedelta(days=1)).isoformat(),
        )
        assert empty.from_ts == earliest
        assert empty.clamped is True

    def test_end_before_available_clamps(self) -> None:
        earliest = _NOW - timedelta(hours=1)
        got = _query(earliest=earliest).resolve(
            window_seconds=3600, end=(_NOW - timedelta(days=1)).isoformat()
        )
        assert got.from_ts == earliest
        assert got.to_ts >= earliest
        assert got.clamped is True

    def test_first_sample_ts_skips_junk_and_errors(self) -> None:
        home = self.tmp_path / "raft"
        path = home / METRICS_DIR / METRICS_FILENAME
        path.parent.mkdir(parents=True)
        archive = path.parent / f"{METRICS_FILENAME}.2026-10-05"
        archive.write_text("not-json\n", encoding="utf-8")
        ts = _NOW - timedelta(minutes=5)
        _MetricsFixtures.write_jsonl(home, [_MetricsFixtures.sample(ts, cpu=9)])
        reader = MetricsJsonlReader(path)
        assert reader.earliest_ts() == ts
        assert reader._first_sample_ts(path.parent) is None
        path.write_text('{"ts":"nope"}\n', encoding="utf-8")
        assert reader._first_sample_ts(path) is None
