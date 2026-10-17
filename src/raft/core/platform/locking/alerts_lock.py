"""Flock for CLI/serve writes to ``state/alerts/rules.yaml``."""

from pathlib import Path
from typing import Optional

from .exclusive import ExclusiveLock
from .paths import LockPaths


class AlertsLock(ExclusiveLock):
    """Serialize alert rules document writes."""

    def __init__(self, root: Path, *, timeout: Optional[float] = None) -> None:
        super().__init__(
            LockPaths(root).alerts(),
            kind="alerts",
            timeout=timeout,
        )
