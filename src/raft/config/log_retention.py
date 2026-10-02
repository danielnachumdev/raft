"""Prune ``raft.log`` by max age and max size (oldest lines first)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

WallClock = Callable[[], datetime]
SECONDS_PER_DAY = 86400.0
_ASCTIME_FMT = "%Y-%m-%d %H:%M:%S"
_ASCTIME_LEN = 19


class LogRetention:
    """Drop oldest structured log lines until age and size limits both hold.

    Timestamps are the leading ``%(asctime)s`` field (``datefmt``
    ``%Y-%m-%d %H:%M:%S``, naive local). Lines without a parseable prefix are
    treated as ancient and dropped first under age pruning.
    """

    def __init__(
        self,
        *,
        max_age_days: int,
        max_bytes: int,
        wall_clock: Optional[WallClock] = None,
    ) -> None:
        self.max_age_seconds = float(max_age_days) * SECONDS_PER_DAY
        self.max_bytes = int(max_bytes)
        self._wall_clock = wall_clock or datetime.now

    def prune(self, path: Path) -> None:
        if not path.is_file() or self.max_bytes < 1:
            return
        kept = self._lines_within_age(path)
        kept = self._trim_to_max_bytes(kept)
        self._rewrite(path, kept)

    def _lines_within_age(self, path: Path) -> List[str]:
        cutoff = self._wall_clock() - timedelta(seconds=self.max_age_seconds)
        kept: List[str] = []
        with path.open(encoding="utf-8") as handle:
            for raw in handle:
                line = raw.rstrip("\n")
                if not line:
                    continue
                if self._line_ts(line) >= cutoff:
                    kept.append(line)
        return kept

    def _trim_to_max_bytes(self, lines: List[str]) -> List[str]:
        total = sum(len(line) + 1 for line in lines)
        drop = 0
        while drop < len(lines) and total > self.max_bytes:
            total -= len(lines[drop]) + 1
            drop += 1
        return lines[drop:]

    def _rewrite(self, path: Path, lines: List[str]) -> None:
        text = "".join(line + "\n" for line in lines)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
        logger.debug("log retention pruned path=%s lines=%s", path, len(lines))

    @staticmethod
    def _line_ts(line: str) -> datetime:
        if len(line) < _ASCTIME_LEN:
            return datetime.min
        try:
            return datetime.strptime(line[:_ASCTIME_LEN], _ASCTIME_FMT)
        except ValueError:
            return datetime.min
