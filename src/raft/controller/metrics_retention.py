"""Prune ``resources.jsonl`` by max age and max size (oldest first)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

WallClock = Callable[[], datetime]
SECONDS_PER_DAY = 86400.0


class MetricsRetention:
    """Drop oldest JSONL samples until age and size limits both hold."""

    def __init__(
        self,
        *,
        max_age_days: int,
        max_bytes: int,
        wall_clock: Optional[WallClock] = None,
    ) -> None:
        self.max_age_seconds = float(max_age_days) * SECONDS_PER_DAY
        self.max_bytes = int(max_bytes)
        self._wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))

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
        total = sum(len(line) + 1 for line in lines)  # +1 newline
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
        logger.debug("metrics retention pruned path=%s lines=%s", path, len(lines))

    @staticmethod
    def _line_ts(line: str) -> datetime:
        try:
            payload = json.loads(line)
            raw = payload.get("ts")
            if isinstance(raw, str) and raw:
                return MetricsRetention._parse_ts(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        return datetime.min.replace(tzinfo=timezone.utc)

    @staticmethod
    def _parse_ts(raw: str) -> datetime:
        text = raw.replace("Z", "+00:00")
        when = datetime.fromisoformat(text)
        if when.tzinfo is None:
            return when.replace(tzinfo=timezone.utc)
        return when.astimezone(timezone.utc)
