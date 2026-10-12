"""Flock for serve notification channel writes to ``settings.yaml``."""

from pathlib import Path
from typing import Optional

from .exclusive import ExclusiveLock
from .paths import LockPaths


class NotificationsLock(ExclusiveLock):
    """Serialize serve notification channel writes to ``settings.yaml``."""

    def __init__(self, root: Path, *, timeout: Optional[float] = None) -> None:
        super().__init__(
            LockPaths(root).notifications(),
            kind="notifications",
            timeout=timeout,
        )
