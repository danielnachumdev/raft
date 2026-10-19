"""Flock for ``settings.yaml`` ``dashboard:`` writes."""

from pathlib import Path
from typing import Optional

from .exclusive import ExclusiveLock
from .paths import LockPaths


class DashboardLock(ExclusiveLock):
    """Serialize dashboard settings writes to ``settings.yaml``."""

    def __init__(self, root: Path, *, timeout: Optional[float] = None) -> None:
        super().__init__(
            LockPaths(root).dashboard(),
            kind="dashboard",
            timeout=timeout,
        )
