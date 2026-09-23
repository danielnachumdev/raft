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


def _read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _parse_meminfo(text: str) -> Optional[HostMemory]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        parts = rest.split()
        if not parts or not parts[0].isdigit():
            continue
        # Values are KiB.
        values[key.strip()] = int(parts[0]) * 1024
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


def _parse_loadavg(text: str) -> Optional[Tuple[float, float, float]]:
    parts = text.split()
    if len(parts) < 3:
        return None
    try:
        return (float(parts[0]), float(parts[1]), float(parts[2]))
    except ValueError:
        return None


def _parse_uptime(text: str) -> Optional[float]:
    parts = text.split()
    if not parts:
        return None
    try:
        return float(parts[0])
    except ValueError:
        return None


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


def collect_host_resources(
    *,
    disk_path: Optional[Path] = None,
    proc: Path = Path("/proc"),
) -> HostResources:
    """Read host CPU/memory/disk/uptime. Missing ``/proc`` fields become ``None``."""
    meminfo = _read_text(proc / "meminfo")
    loadavg = _read_text(proc / "loadavg")
    uptime = _read_text(proc / "uptime")
    target = disk_path if disk_path is not None else Path("/")
    cpus = os.cpu_count()
    return HostResources(
        cpus=cpus,
        loadavg=_parse_loadavg(loadavg) if loadavg is not None else None,
        memory=_parse_meminfo(meminfo) if meminfo is not None else None,
        disk=_disk_for(target),
        uptime_seconds=_parse_uptime(uptime) if uptime is not None else None,
    )


def parse_docker_size(value: str) -> Optional[int]:
    """Parse docker human sizes (``1.5MiB``, ``64MB``, ``1024B``) to bytes."""
    text = (value or "").strip()
    if not text or text in ("--", "0"):
        return 0 if text == "0" else None
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
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_docker_pair(value: str) -> tuple[Optional[int], Optional[int]]:
    """Parse ``a / b`` pairs from ``docker stats`` (MemUsage, NetIO, BlockIO)."""
    text = (value or "").strip()
    if " / " not in text:
        return (parse_docker_size(text), None)
    left, right = text.split(" / ", 1)
    return (parse_docker_size(left), parse_docker_size(right))


def parse_percent(value: str) -> Optional[float]:
    text = (value or "").strip().rstrip("%")
    if not text or text == "--":
        return None
    try:
        return float(text)
    except ValueError:
        return None
