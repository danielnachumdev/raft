"""File handler that rolls on local day change or ``max_bytes``."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

from .archive_names import LogArchiveNames

logger = logging.getLogger(__name__)

WallClock = Callable[[], datetime]


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
