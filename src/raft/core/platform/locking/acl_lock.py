"""Flock for serve firewall document writes."""

from pathlib import Path
from typing import Optional

from .exclusive import ExclusiveLock
from .paths import LockPaths


class AclLock(ExclusiveLock):
    """Serialize serve firewall mutations before render/reload."""

    def __init__(self, root: Path, *, timeout: Optional[float] = None) -> None:
        super().__init__(
            LockPaths(root).acl(),
            kind="acl",
            timeout=timeout,
        )
