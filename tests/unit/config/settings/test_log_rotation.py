"""Host CLI log rotation: daily seals, same-day parts, age cleanup."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from raft.config.log_rotation import (
    LogArchiveNames,
    LogArchiveRetention,
    LogRotatingFileHandler,
    LogRotationBootstrap,
)


class TestLogArchiveNames:
    def test_part_one_is_date_only(self, tmp_path: Path) -> None:
        names = LogArchiveNames(tmp_path / "raft.log")
        assert names.archive_for(date(2026, 10, 3), 1) == tmp_path / "raft.log.2026-10-03"

    def test_part_two_uses_numeric_suffix(self, tmp_path: Path) -> None:
        names = LogArchiveNames(tmp_path / "raft.log")
        assert names.archive_for(date(2026, 10, 3), 2) == tmp_path / "raft.log.2026-10-03.2"

    def test_next_archive_skips_existing_parts(self, tmp_path: Path) -> None:
        names = LogArchiveNames(tmp_path / "raft.log")
        (tmp_path / "raft.log.2026-10-03").write_text("a\n", encoding="utf-8")
        (tmp_path / "raft.log.2026-10-03.2").write_text("b\n", encoding="utf-8")
        assert names.next_archive(date(2026, 10, 3)) == tmp_path / "raft.log.2026-10-03.3"

    def test_parse_day_rejects_unrelated_files(self, tmp_path: Path) -> None:
        names = LogArchiveNames(tmp_path / "raft.log")
        assert names.parse_day(tmp_path / "other.log.2026-10-03") is None
        assert names.parse_day(tmp_path / "raft.log.tmp") is None
        assert names.parse_day(tmp_path / "raft.log.2026-10-03") == date(2026, 10, 3)
        assert names.parse_day(tmp_path / "raft.log.2026-10-03.2") == date(2026, 10, 3)

    def test_parse_day_rejects_invalid_calendar_date(self, tmp_path: Path) -> None:
        names = LogArchiveNames(tmp_path / "raft.log")
        assert names.parse_day(tmp_path / "raft.log.2026-02-30") is None

    def test_parse_part_defaults_and_suffix(self, tmp_path: Path) -> None:
        names = LogArchiveNames(tmp_path / "raft.log")
        assert names.parse_part(tmp_path / "raft.log.2026-10-03") == 1
        assert names.parse_part(tmp_path / "raft.log.2026-10-03.2") == 2
        assert names.parse_part(tmp_path / "other.log.2026-10-03") is None


class TestLogArchiveRetention:
    def test_deletes_archives_older_than_max_days(self, tmp_path: Path) -> None:
        active = tmp_path / "raft.log"
        keep = tmp_path / "raft.log.2026-05-20"
        drop = tmp_path / "raft.log.2026-04-01"
        drop_part = tmp_path / "raft.log.2026-04-01.2"
        for path in (keep, drop, drop_part):
            path.write_text("x\n", encoding="utf-8")
        now = datetime(2026, 6, 1, 12, 0, 0)
        LogArchiveRetention(max_age_days=30, wall_clock=lambda: now).cleanup(active)
        assert keep.exists() and not drop.exists() and not drop_part.exists()

    def test_noop_when_max_age_non_positive(self, tmp_path: Path) -> None:
        archive = tmp_path / "raft.log.2020-01-01"
        archive.write_text("x\n", encoding="utf-8")
        LogArchiveRetention(max_age_days=0).cleanup(tmp_path / "raft.log")
        assert archive.exists()

    def test_unlink_oserror_is_swallowed(self, tmp_path: Path) -> None:
        archive = tmp_path / "raft.log.2020-01-01"
        archive.write_text("x\n", encoding="utf-8")
        now = datetime(2026, 6, 1, 12, 0, 0)
        with patch.object(Path, "unlink", side_effect=OSError("busy")):
            LogArchiveRetention(max_age_days=1, wall_clock=lambda: now).cleanup(
                tmp_path / "raft.log"
            )

    def test_cleanup_when_parent_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "no-such-dir" / "raft.log"
        LogArchiveRetention(max_age_days=30).cleanup(missing)


class TestLogRotationBootstrap:
    def test_seals_oversized_active_without_rewrite(self, tmp_path: Path) -> None:
        active = tmp_path / "raft.log"
        payload = "x" * 200
        active.write_text(payload, encoding="utf-8")
        now = datetime(2026, 10, 3, 15, 0, 0)
        LogRotationBootstrap(
            max_age_days=30, max_bytes=100, wall_clock=lambda: now
        ).prepare(active)
        assert not active.exists()
        sealed = tmp_path / "raft.log.2026-10-03"
        assert sealed.read_text(encoding="utf-8") == payload

    def test_seals_previous_day_active_by_mtime(self, tmp_path: Path) -> None:
        active = tmp_path / "raft.log"
        active.write_text("yesterday\n", encoding="utf-8")
        stamp = datetime(2026, 10, 2, 18, 0, 0).timestamp()
        os.utime(active, (stamp, stamp))
        now = datetime(2026, 10, 3, 9, 0, 0)
        LogRotationBootstrap(
            max_age_days=30, max_bytes=10_000_000, wall_clock=lambda: now
        ).prepare(active)
        assert (tmp_path / "raft.log.2026-10-02").read_text(encoding="utf-8") == "yesterday\n"

    def test_cleans_old_archives_on_prepare(self, tmp_path: Path) -> None:
        old = tmp_path / "raft.log.2026-01-01"
        old.write_text("old\n", encoding="utf-8")
        now = datetime(2026, 10, 3, 12, 0, 0)
        LogRotationBootstrap(
            max_age_days=30, max_bytes=10_000_000, wall_clock=lambda: now
        ).prepare(tmp_path / "raft.log")
        assert not old.exists()

    def test_skips_missing_or_empty_active(self, tmp_path: Path) -> None:
        active = tmp_path / "raft.log"
        LogRotationBootstrap(max_age_days=30, max_bytes=100).prepare(active)
        active.write_text("", encoding="utf-8")
        LogRotationBootstrap(max_age_days=30, max_bytes=100).prepare(active)
        assert active.exists()

    def test_keeps_today_active_under_max_bytes(self, tmp_path: Path) -> None:
        active = tmp_path / "raft.log"
        active.write_text("keep-me\n", encoding="utf-8")
        now = datetime(2026, 10, 3, 12, 0, 0)
        stamp = now.timestamp()
        os.utime(active, (stamp, stamp))
        LogRotationBootstrap(
            max_age_days=30, max_bytes=10_000_000, wall_clock=lambda: now
        ).prepare(active)
        assert active.read_text(encoding="utf-8") == "keep-me\n"


class TestLogRotatingFileHandler:
    def _handler(self, path: Path, *, max_bytes: int, clock: list) -> LogRotatingFileHandler:
        return LogRotatingFileHandler(
            path, max_bytes=max_bytes, wall_clock=lambda: clock[0]
        )

    def _emit(self, handler: LogRotatingFileHandler, msg: str) -> None:
        record = logging.LogRecord(
            name="raft.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )
        handler.emit(record)

    def test_day_rollover_seals_with_date_suffix(self, tmp_path: Path) -> None:
        path = tmp_path / "raft.log"
        clock = [datetime(2026, 10, 3, 23, 59, 0)]
        handler = self._handler(path, max_bytes=10_000_000, clock=clock)
        self._emit(handler, "day-one")
        clock[0] = datetime(2026, 10, 4, 0, 1, 0)
        self._emit(handler, "day-two")
        handler.close()
        assert "day-one" in (tmp_path / "raft.log.2026-10-03").read_text(encoding="utf-8")
        assert "day-two" in path.read_text(encoding="utf-8")

    def test_size_split_same_day_uses_part_suffix(self, tmp_path: Path) -> None:
        path = tmp_path / "raft.log"
        clock = [datetime(2026, 10, 3, 12, 0, 0)]
        handler = self._handler(path, max_bytes=20, clock=clock)
        self._emit(handler, "a" * 30)
        self._emit(handler, "b" * 5)
        handler.close()
        part1 = tmp_path / "raft.log.2026-10-03"
        assert "a" * 30 in part1.read_text(encoding="utf-8")
        assert "b" * 5 in path.read_text(encoding="utf-8")

    def test_second_size_split_uses_dot_two(self, tmp_path: Path) -> None:
        path = tmp_path / "raft.log"
        clock = [datetime(2026, 10, 3, 12, 0, 0)]
        handler = self._handler(path, max_bytes=20, clock=clock)
        self._emit(handler, "one" + ("x" * 20))
        self._emit(handler, "two" + ("x" * 20))
        self._emit(handler, "three")
        handler.close()
        assert (tmp_path / "raft.log.2026-10-03").exists()
        assert (tmp_path / "raft.log.2026-10-03.2").exists()
        assert "three" in path.read_text(encoding="utf-8")

    def test_emit_handles_rollover_errors(self, tmp_path: Path) -> None:
        path = tmp_path / "raft.log"
        clock = [datetime(2026, 10, 3, 12, 0, 0)]
        handler = self._handler(path, max_bytes=10, clock=clock)
        self._emit(handler, "seed-message")
        with patch.object(handler, "_rollover", side_effect=RuntimeError("boom")):
            self._emit(handler, "after-error")
        handler.close()

    def test_stream_size_zero_when_closed(self, tmp_path: Path) -> None:
        path = tmp_path / "raft.log"
        handler = LogRotatingFileHandler(path, max_bytes=100)
        handler.close()
        assert handler._stream_size() == 0

    def test_rollover_with_closed_stream_and_empty_active(self, tmp_path: Path) -> None:
        path = tmp_path / "raft.log"
        handler = LogRotatingFileHandler(
            path, max_bytes=100, wall_clock=lambda: datetime(2026, 10, 3, 12, 0, 0)
        )
        handler.close()
        handler._rollover(date(2026, 10, 3))
        assert path.exists()
        handler.close()
