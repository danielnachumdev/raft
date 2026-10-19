"""Flock for any writer of ``~/.raft/settings.yaml``."""

from pathlib import Path
from typing import Optional

from .exclusive import ExclusiveLock
from .paths import LockPaths


class SettingsLock(ExclusiveLock):
    """Serialize all mutative rewrites of operator ``settings.yaml``."""

    def __init__(self, root: Path, *, timeout: Optional[float] = None) -> None:
        super().__init__(
            LockPaths(root).settings(),
            kind="settings",
            timeout=timeout,
        )
