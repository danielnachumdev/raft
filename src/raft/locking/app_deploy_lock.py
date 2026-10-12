"""Per-app flock for apply deploy / redeploy / cutover."""

from pathlib import Path
from typing import Optional

from .exclusive import ExclusiveLock
from .paths import LockPaths


class AppDeployLock(ExclusiveLock):
    """Serialize mutative work for one app (apply deploy / redeploy / cutover)."""

    def __init__(
        self,
        root: Path,
        name: str,
        *,
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(
            LockPaths(root).app(name),
            kind=f"app {name!r}",
            timeout=timeout,
        )
