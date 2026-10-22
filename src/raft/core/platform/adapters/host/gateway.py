"""Shared gateway for host-machine facts (identity + resource probes)."""

import socket
from pathlib import Path
from typing import Callable, Optional

from .models import HostResources
from .probe import HostProbe

# Mounted from the VM ``/etc/hostname`` into the dashboard container (see compose).
_HOST_HOSTNAME_PATH = Path("/etc/host_hostname")


class HostGateway:
    """Single source of truth for host hostname and resource snapshots."""

    def __init__(
        self,
        *,
        disk_path: Optional[Path] = None,
        proc: Path = Path("/proc"),
        gethostname: Callable[[], str] = socket.gethostname,
        getfqdn: Callable[[str], str] = socket.getfqdn,
        host_hostname_path: Path = _HOST_HOSTNAME_PATH,
    ) -> None:
        self._probe = HostProbe(disk_path=disk_path, proc=proc)
        self._gethostname = gethostname
        self._getfqdn = getfqdn
        self._host_hostname_path = host_hostname_path

    def hostname(self) -> str:
        """Short machine name (VM OS), never a Docker short container id."""
        return self._short_name(self._raw_hostname())

    def fqdn(self) -> Optional[str]:
        """FQDN when it differs from the short name; else ``None``."""
        short = self.hostname()
        raw = self._raw_hostname()
        if "." in raw and self._short_name(raw) == short:
            return raw
        resolved = self._getfqdn(short).strip()
        if resolved and resolved != short and "." in resolved:
            return resolved
        return None

    def resources(self) -> HostResources:
        """CPU / memory / disk / uptime from ``/proc`` and ``shutil``."""
        return self._probe.collect()

    def _raw_hostname(self) -> str:
        from_file = self._read_host_hostname_file()
        if from_file:
            return from_file
        return self._gethostname().strip()

    def _read_host_hostname_file(self) -> Optional[str]:
        path = self._host_hostname_path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        line = text.splitlines()[0].strip() if text else ""
        return line or None

    @staticmethod
    def _short_name(name: str) -> str:
        return name.split(".", 1)[0] if name else name
