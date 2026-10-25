"""Flock for CLI/serve writes to ``host/inbox/`` read-state."""

from pathlib import Path
from typing import Optional

from .exclusive import ExclusiveLock
from .paths import LockPaths


class InboxLock(ExclusiveLock):
    """Serialize operator-inbox read-state document writes."""

    def __init__(self, root: Path, *, timeout: Optional[float] = None) -> None:
        super().__init__(
            LockPaths(root).inbox(),
            kind="inbox",
            timeout=timeout,
        )
