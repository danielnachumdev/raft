"""Active ``raft.log`` plus dated sealed archive path helpers."""

import re
from datetime import date
from pathlib import Path
from typing import Optional

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
        match = self._match(path)
        if match is None:
            return None
        try:
            return date.fromisoformat(match.group("day"))
        except ValueError:
            return None

    def parse_part(self, path: Path) -> Optional[int]:
        match = self._match(path)
        if match is None:
            return None
        raw = match.group("part")
        return 1 if raw is None else int(raw)

    def _match(self, path: Path):
        match = _ARCHIVE_NAME.match(path.name)
        if match is None or match.group("base") != self.active.name:
            return None
        return match
