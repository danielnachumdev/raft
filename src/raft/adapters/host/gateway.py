"""Shared gateway for host-machine facts (identity + resource probes)."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Callable, Optional

from .models import HostResources
from .probe import HostProbe


class HostGateway:
    """Single source of truth for host hostname and resource snapshots."""

    def __init__(
        self,
        *,
        disk_path: Optional[Path] = None,
        proc: Path = Path("/proc"),
        gethostname: Callable[[], str] = socket.gethostname,
    ) -> None:
        self._probe = HostProbe(disk_path=disk_path, proc=proc)
        self._gethostname = gethostname

    def hostname(self) -> str:
        """Short machine name (``socket.gethostname()`` by default)."""
        return self._gethostname()

    def resources(self) -> HostResources:
        """CPU / memory / disk / uptime from ``/proc`` and ``shutil``."""
        return self._probe.collect()
