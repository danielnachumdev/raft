"""Cheap log setup: seal stale/oversized active file; purge old archives."""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Optional

from .archive_names import LogArchiveNames
from .archive_retention import LogArchiveRetention

logger = logging.getLogger(__name__)

WallClock = Callable[[], datetime]


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
