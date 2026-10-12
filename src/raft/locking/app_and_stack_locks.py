"""Acquire one app lock then the stack lock (fixed order)."""

from pathlib import Path
from typing import Optional

from .apps_and_stack_locks import AppsAndStackLocks


class AppAndStackLocks(AppsAndStackLocks):
    """Acquire app lock then stack lock (fixed order avoids cross-app deadlock)."""

    def __init__(
        self,
        root: Path,
        name: str,
        *,
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(root, (name,), timeout=timeout)
