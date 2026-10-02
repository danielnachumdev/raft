"""Host capacity / utilization snapshot types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


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
