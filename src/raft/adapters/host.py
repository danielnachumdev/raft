"""Host resource probes (Linux ``/proc`` + ``shutil``; no extra deps)."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple


@dataclass(frozen=True)
class HostMemory:
    total_bytes: int
    available_bytes: int
    used_bytes: int
    used_percent: float


@dataclass(frozen=True)
class HostDisk:
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float


@dataclass(frozen=True)
class HostResources:
    """Point-in-time host capacity and utilization."""

    cpus: Optional[int]
    loadavg: Optional[Tuple[float, float, float]]
    memory: Optional[HostMemory]
    disk: Optional[HostDisk]
    uptime_seconds: Optional[float]


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


class DockerStatsText:
    """Parse human-readable ``docker stats`` size / percent fields."""

    @classmethod
    def parse_size(cls, value: str) -> Optional[int]:
        """Parse docker human sizes (``1.5MiB``, ``64MB``, ``1024B``) to bytes."""
        text = (value or "").strip()
        if not text or text in ("--", "0"):
            return 0 if text == "0" else None
        parsed = cls._size_with_unit(text)
        if parsed is not None:
            return parsed
        try:
            return int(float(text))
        except ValueError:
            return None

    @staticmethod
    def _size_with_unit(text: str) -> Optional[int]:
        units: Sequence[tuple[str, int]] = (
            ("KiB", 1024),
            ("MiB", 1024**2),
            ("GiB", 1024**3),
            ("TiB", 1024**4),
            ("kB", 1000),
            ("MB", 1000**2),
            ("GB", 1000**3),
            ("TB", 1000**4),
            ("B", 1),
        )
        for suffix, factor in units:
            if text.endswith(suffix):
                number = text[: -len(suffix)].strip()
                try:
                    return int(float(number) * factor)
                except ValueError:
                    return None
        return None

    @classmethod
    def parse_pair(cls, value: str) -> tuple[Optional[int], Optional[int]]:
        """Parse ``a / b`` pairs from ``docker stats`` (MemUsage, NetIO, BlockIO)."""
        text = (value or "").strip()
        if " / " not in text:
            return (cls.parse_size(text), None)
        left, right = text.split(" / ", 1)
        return (cls.parse_size(left), cls.parse_size(right))

    @staticmethod
    def parse_percent(value: str) -> Optional[float]:
        text = (value or "").strip().rstrip("%")
        if not text or text == "--":
            return None
        try:
            return float(text)
        except ValueError:
            return None
