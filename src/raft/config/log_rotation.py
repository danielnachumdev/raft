"""Timed + size-split rotation for the host CLI log file."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

WallClock = Callable[[], datetime]
_ARCHIVE_NAME = re.compile(
    r"^(?P<base>.+)\.(?P<day>\d{4}-\d{2}-\d{2})(?:\.(?P<part>[1-9]\d*))?$"
)


class LogArchiveNames:
    """Active ``raft.log`` plus dated sealed parts.

    Sealed part 1: ``raft.log.YYYY-MM-DD``.
    Further same-day parts: ``raft.log.YYYY-MM-DD.2``, ``.3``, …
    """

    def __init__(self, active: Path) -> None:
        self.active = active

    def archive_for(self, day: date, part: int) -> Path:
        base = f"{self.active.name}.{day.isoformat()}"
        if part <= 1:
            return self.active.parent / base
        return self.active.parent / f"{base}.{part}"

    def next_archive(self, day: date) -> Path:
        part = 1
        while self.archive_for(day, part).exists():
            part += 1
        return self.archive_for(day, part)

    def parse_day(self, path: Path) -> Optional[date]:
        match = _ARCHIVE_NAME.match(path.name)
        if match is None or match.group("base") != self.active.name:
            return None
        try:
            return date.fromisoformat(match.group("day"))
        except ValueError:
            return None


class LogArchiveRetention:
    """Delete sealed archives older than ``max_age_days`` (by suffix date)."""

    def __init__(
        self,
        *,
        max_age_days: int,
        wall_clock: Optional[WallClock] = None,
    ) -> None:
        self.max_age_days = int(max_age_days)
        self._wall_clock = wall_clock or datetime.now

    def cleanup(self, active: Path) -> None:
        if self.max_age_days < 1:
            return
        names = LogArchiveNames(active)
        cutoff = self._wall_clock().date() - timedelta(days=self.max_age_days)
        for path in self._iter_archives(active, names):
            day = names.parse_day(path)
            if day is not None and day < cutoff:
                self._unlink(path)

    def _iter_archives(self, active: Path, names: LogArchiveNames) -> List[Path]:
        parent = active.parent
        if not parent.is_dir():
            return []
        return [p for p in parent.iterdir() if p.is_file() and names.parse_day(p)]

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink()
        except OSError:
            logger.debug("log archive remove failed path=%s", path, exc_info=True)
            return
        logger.debug("log archive removed path=%s", path)


class LogRotationBootstrap:
    """Cheap setup: seal stale/oversized active file; purge old archives."""

    def __init__(
        self,
        *,
        max_age_days: int,
        max_bytes: int,
        wall_clock: Optional[WallClock] = None,
    ) -> None:
        self.max_bytes = int(max_bytes)
        self._wall_clock = wall_clock or datetime.now
        self._retention = LogArchiveRetention(
            max_age_days=max_age_days,
            wall_clock=self._wall_clock,
        )

    def prepare(self, active: Path) -> None:
        self._seal_if_needed(active)
        self._retention.cleanup(active)

    def _seal_if_needed(self, active: Path) -> None:
        if not active.is_file() or active.stat().st_size < 1:
            return
        day = datetime.fromtimestamp(active.stat().st_mtime).date()
        today = self._wall_clock().date()
        oversize = self.max_bytes >= 1 and active.stat().st_size >= self.max_bytes
        if day != today or oversize:
            self._seal(active, day)

    @staticmethod
    def _seal(active: Path, day: date) -> None:
        dest = LogArchiveNames(active).next_archive(day)
        active.replace(dest)
        logger.debug("log sealed active=%s archive=%s", active, dest)


class LogRotatingFileHandler(logging.FileHandler):
    """Append to the active log; roll on local day change or ``max_bytes``."""

    def __init__(
        self,
        filename: Path,
        *,
        max_bytes: int,
        wall_clock: Optional[WallClock] = None,
        encoding: str = "utf-8",
    ) -> None:
        self.max_bytes = int(max_bytes)
        self._wall_clock = wall_clock or datetime.now
        self._names = LogArchiveNames(Path(filename))
        self._current_day = self._wall_clock().date()
        super().__init__(str(filename), encoding=encoding)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._maybe_rollover()
        except Exception:
            self.handleError(record)
            return
        super().emit(record)

    def _maybe_rollover(self) -> None:
        today = self._wall_clock().date()
        if today != self._current_day:
            self._rollover(self._current_day)
            self._current_day = today
            return
        if self.max_bytes >= 1 and self._stream_size() >= self.max_bytes:
            self._rollover(today)

    def _stream_size(self) -> int:
        if self.stream is None:
            return 0
        self.stream.flush()
        return int(self.stream.tell())

    def _rollover(self, day: date) -> None:
        if self.stream is not None:
            self.stream.close()
            self.stream = None
        active = self._names.active
        if active.is_file() and active.stat().st_size > 0:
            dest = self._names.next_archive(day)
            active.replace(dest)
            logger.debug("log rotated archive=%s", dest)
        self.stream = self._open()
