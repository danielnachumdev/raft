"""Rotate ``resources.jsonl`` like host CLI logs (seal; never rewrite)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from raft.config.log_rotation import LogRotationBootstrap

WallClock = Callable[[], datetime]


class MetricsRotation:
    """Seal oversized/stale active file; drop sealed archives by age.

    Reuses log archive naming (``resources.jsonl.YYYY-MM-DD[.N]``) and
    ``LogRotationBootstrap`` so retention never loads JSONL into memory.
    """

    def __init__(
        self,
        *,
        max_age_days: int,
        max_bytes: int,
        wall_clock: Optional[WallClock] = None,
    ) -> None:
        self._bootstrap = LogRotationBootstrap(
            max_age_days=max_age_days,
            max_bytes=int(max_bytes),
            wall_clock=wall_clock or datetime.now,
        )

    def maintain(self, active: Path) -> None:
        """Prepare before append: seal if needed, then age-delete archives."""
        self._bootstrap.prepare(active)
