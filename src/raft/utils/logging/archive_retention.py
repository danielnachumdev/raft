"""Delete sealed log archives older than the configured age."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, List, Optional

from .archive_names import LogArchiveNames

logger = logging.getLogger(__name__)

WallClock = Callable[[], datetime]


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
