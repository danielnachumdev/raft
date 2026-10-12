"""Stack-wide flock for render / nginx / compose / cutover / purge."""

from pathlib import Path
from typing import Optional

from .exclusive import ExclusiveLock
from .paths import LockPaths


class StackLock(ExclusiveLock):
    """Serialize render / nginx reload / compose / cutover across all apps."""

    def __init__(self, root: Path, *, timeout: Optional[float] = None) -> None:
        super().__init__(
            LockPaths(root).stack(),
            kind="stack",
            timeout=timeout,
        )
