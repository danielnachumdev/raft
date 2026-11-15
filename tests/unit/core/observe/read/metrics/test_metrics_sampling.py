"""Time-bucketed sampling for wide Trends windows (lazy JSON parse)."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

from raft.services.controller.jobs.metrics import METRICS_DIR, METRICS_FILENAME
from raft.core.observe.read.metrics import MetricsJsonlReader, MetricsRead
from raft.core.observe.read.metrics.buckets import MetricsSampleBuckets
from raft.core.observe.read.metrics.window import ResolvedMetricsRange

from tests.unit.base import RaftTestCase
from . import fixtures as metrics_fx

_NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


def _writer_row(ts: datetime, n: int) -> Dict[str, Any]:
    # Controller writer order: payload first, ``ts`` appended last.
    return {"host": {"cpus": 2}, "containers": [], "n": n, "ts": ts.isoformat()}


def _write(path: Path, rows: List[Dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows),
        encoding="utf-8",
    )
    return path


class TestMetricsSampling(RaftTestCase):
    def _minutes(self, count: int) -> Path:
        rows = [_writer_row(_NOW - timedelta(minutes=count - i), i) for i in range(count)]
        return _write(self.tmp_path / METRICS_DIR / METRICS_FILENAME, rows)

    def test_bucketed_keeps_newest_per_bucket_and_skips_parsing(self) -> None:
        reader = MetricsJsonlReader(self._minutes(60))
        with patch.object(
            MetricsJsonlReader, "_parse_line", wraps=MetricsJsonlReader._parse_line
        ) as parse:
            got = reader.samples_in_window(
                from_ts=_NOW - timedelta(hours=1), bucket_seconds=600
            )
        assert [s["n"] for s in got] == [9, 19, 29, 39, 49, 59]
        assert parse.call_count == 6

    def test_zero_bucket_keeps_every_sample(self) -> None:
        reader = MetricsJsonlReader(self._minutes(10))
        got = reader.samples_in_window(from_ts=_NOW - timedelta(hours=1))
        assert [s["n"] for s in got] == list(range(10))

    def test_bad_line_in_bucket_falls_through_to_next_sample(self) -> None:
        path = self._minutes(3)
        lines = path.read_text(encoding="utf-8").splitlines()
        newest_ts = (_NOW - timedelta(minutes=1)).isoformat()
        lines[-1] = '{"n":,"ts":"' + newest_ts + '"}'
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        got = MetricsJsonlReader(path).samples_in_window(
            from_ts=_NOW - timedelta(hours=1), bucket_seconds=3600
        )
        assert [s["n"] for s in got] == [1]

    def test_non_trailing_ts_falls_back_to_full_parse(self) -> None:
        rows = [metrics_fx.sample(_NOW - timedelta(minutes=m)) for m in (3, 2, 1)]
        path = _write(self.tmp_path / METRICS_DIR / METRICS_FILENAME, rows)
        got = MetricsJsonlReader(path).samples_in_window(
            from_ts=_NOW - timedelta(hours=1), bucket_seconds=3600
        )
        assert len(got) == 1
        assert got[0]["ts"] == rows[-1]["ts"]

    def test_lines_without_any_ts_are_skipped(self) -> None:
        path = _write(
            self.tmp_path / METRICS_DIR / METRICS_FILENAME,
            [_writer_row(_NOW - timedelta(minutes=1), 1), {"n": 2}, {"ts": 5}],
        )
        got = MetricsJsonlReader(path).samples_in_window(from_ts=_NOW - timedelta(hours=1))
        assert [s["n"] for s in got] == [1]

    def test_latest_sample_skips_empty_active_and_bad_lines(self) -> None:
        path = self.tmp_path / METRICS_DIR / METRICS_FILENAME
        archive = path.parent / f"{METRICS_FILENAME}.2026-10-01"
        _write(archive, [_writer_row(_NOW - timedelta(days=1), 7)])
        with archive.open("a", encoding="utf-8") as handle:
            handle.write("not-json\n")
        path.write_text("", encoding="utf-8")
        latest = MetricsJsonlReader(path).latest_sample()
        assert latest is not None and latest["n"] == 7

    def test_trailing_ts_rejects_non_terminal_or_escaped_values(self) -> None:
        trailing = MetricsJsonlReader.trailing_ts
        assert trailing('{"a":1,"ts":"2026-10-02T12:00:00+00:00"}\n') == (
            "2026-10-02T12:00:00+00:00"
        )
        assert trailing('{"ts":"x","b":"y"}') is None
        assert trailing('{"a":{"ts":"x"}}') is None
        assert trailing('{"b":"y"}') is None
        assert trailing('{"ts":"a\\"b"}') is None

    def test_history_wide_window_caps_parsed_samples(self) -> None:
        self._minutes(600)
        payload = MetricsRead(self.tmp_path).history(
            window_seconds=86400, now=_NOW, max_points=20
        )
        host = next(s for s in payload["series"] if s["id"] == "host")
        assert len(host["points"]) == 20
        assert payload["cursor"] == (_NOW - timedelta(minutes=1)).isoformat()

    def test_history_since_poll_keeps_every_new_sample(self) -> None:
        self._minutes(30)
        since = (_NOW - timedelta(minutes=11)).isoformat()
        payload = MetricsRead(self.tmp_path).history(
            window_seconds=86400, since=since, now=_NOW, max_points=12
        )
        host = next(s for s in payload["series"] if s["id"] == "host")
        assert len(host["points"]) == 10


class TestBucketSeconds:
    def _range(self) -> ResolvedMetricsRange:
        return ResolvedMetricsRange(
            from_ts=_NOW - timedelta(hours=10),
            to_ts=_NOW,
            window_seconds=36000,
            clamped=False,
            clamp_message=None,
        )

    def test_full_fetch_oversamples_window(self) -> None:
        assert self._range().bucket_seconds(100) == 36000 / 200

    def test_spans_only_retained_data(self) -> None:
        got = self._range().bucket_seconds(100, earliest=_NOW - timedelta(hours=1))
        assert got == 3600 / 200

    def test_disabled_for_since_and_non_positive_points(self) -> None:
        assert self._range().bucket_seconds(100, since=_NOW) == 0.0
        assert self._range().bucket_seconds(0) == 0.0

    def test_earliest_after_end_clamps_to_zero(self) -> None:
        assert self._range().bucket_seconds(10, earliest=_NOW + timedelta(hours=1)) == 0.0


class TestMetricsSampleBuckets:
    def test_disabled_never_taken(self) -> None:
        buckets = MetricsSampleBuckets(_NOW, 0)
        buckets.claim(_NOW)
        assert not buckets.is_taken(_NOW)

    def test_claim_marks_slot(self) -> None:
        buckets = MetricsSampleBuckets(_NOW, 60)
        buckets.claim(_NOW + timedelta(seconds=30))
        assert buckets.is_taken(_NOW + timedelta(seconds=59))
        assert not buckets.is_taken(_NOW + timedelta(seconds=60))
