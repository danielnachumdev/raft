"""Host resource probes (Linux ``/proc`` + ``shutil``; no extra deps)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional, Tuple

from .models import HostDisk, HostMemory, HostResources


class HostProbe:
    """Read CPU / memory / disk / uptime from ``/proc`` and ``shutil``."""

    def __init__(
        self,
        *,
        disk_path: Optional[Path] = None,
        proc: Path = Path("/proc"),
    ) -> None:
        self.disk_path = disk_path if disk_path is not None else Path("/")
        self.proc = proc

    def collect(self) -> HostResources:
        """Missing ``/proc`` fields become ``None``."""
        meminfo = self._read_text(self.proc / "meminfo")
        loadavg = self._read_text(self.proc / "loadavg")
        uptime = self._read_text(self.proc / "uptime")
        return HostResources(
            cpus=os.cpu_count(),
            loadavg=self._parse_loadavg(loadavg) if loadavg is not None else None,
            memory=self._parse_meminfo(meminfo) if meminfo is not None else None,
            disk=self._disk_for(self.disk_path),
            uptime_seconds=self._parse_uptime(uptime) if uptime is not None else None,
        )

    @staticmethod
    def _read_text(path: Path) -> Optional[str]:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

    def _parse_meminfo(self, text: str) -> Optional[HostMemory]:
        values = self._meminfo_kib_to_bytes(text)
        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        if total is None or available is None or total <= 0:
            return None
        used = max(0, total - available)
        return HostMemory(
            total_bytes=total,
            available_bytes=available,
            used_bytes=used,
            used_percent=round(100.0 * used / total, 2),
        )

    @staticmethod
    def _meminfo_kib_to_bytes(text: str) -> dict[str, int]:
        values: dict[str, int] = {}
        for line in text.splitlines():
            if ":" not in line:
                continue
            key, rest = line.split(":", 1)
            parts = rest.split()
            if not parts or not parts[0].isdigit():
                continue
            values[key.strip()] = int(parts[0]) * 1024
        return values

    @staticmethod
    def _parse_loadavg(text: str) -> Optional[Tuple[float, float, float]]:
        parts = text.split()
        if len(parts) < 3:
            return None
        try:
            return (float(parts[0]), float(parts[1]), float(parts[2]))
        except ValueError:
            return None

    @staticmethod
    def _parse_uptime(text: str) -> Optional[float]:
        parts = text.split()
        if not parts:
            return None
        try:
            return float(parts[0])
        except ValueError:
            return None

    @staticmethod
    def _disk_for(path: Path) -> Optional[HostDisk]:
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            return None
        if usage.total <= 0:
            return None
        used = usage.total - usage.free
        return HostDisk(
            path=str(path),
            total_bytes=usage.total,
            used_bytes=used,
            free_bytes=usage.free,
            used_percent=round(100.0 * used / usage.total, 2),
        )
