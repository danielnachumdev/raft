"""Point-in-time host + container resource snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

# Matches ``x-resources-edge`` in ``share/compose.yaml``.
EDGE_CPUS_LIMIT = "0.25"
EDGE_MEMORY_LIMIT = "32M"
EDGE_CPUS_RESERVATION = "0.05"
EDGE_MEMORY_RESERVATION = "16M"

# Matches ``x-resources-controller`` in ``share/compose.yaml``.
CONTROLLER_CPUS_LIMIT = "0.25"
CONTROLLER_MEMORY_LIMIT = "128M"
CONTROLLER_CPUS_RESERVATION = "0.05"
CONTROLLER_MEMORY_RESERVATION = "32M"


@dataclass(frozen=True)
class AllocatedResources:
    """Declared Compose limits/reservations for a service."""

    cpus_limit: str
    memory_limit: str
    cpus_reservation: str
    memory_reservation: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class MemoryUsage:
    used_bytes: Optional[int]
    limit_bytes: Optional[int]
    used_percent: Optional[float]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IoPair:
    rx_or_read_bytes: Optional[int]
    tx_or_write_bytes: Optional[int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rx_or_read_bytes": self.rx_or_read_bytes,
            "tx_or_write_bytes": self.tx_or_write_bytes,
        }


@dataclass(frozen=True)
class ContainerStats:
    """One Compose service's runtime usage + declared allocation."""

    service: str
    role: str  # gate | router | app
    app: Optional[str]
    group: Optional[str]
    status: str
    uptime_seconds: Optional[float]
    cpu_percent: Optional[float]
    memory: MemoryUsage
    allocated: AllocatedResources
    network: IoPair
    block_io: IoPair
    pids: Optional[int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "role": self.role,
            "app": self.app,
            "group": self.group,
            "status": self.status,
            "uptime_seconds": self.uptime_seconds,
            "cpu_percent": self.cpu_percent,
            "memory": self.memory.to_dict(),
            "allocated": self.allocated.to_dict(),
            "network": {
                "rx_bytes": self.network.rx_or_read_bytes,
                "tx_bytes": self.network.tx_or_write_bytes,
            },
            "block_io": {
                "read_bytes": self.block_io.rx_or_read_bytes,
                "write_bytes": self.block_io.tx_or_write_bytes,
            },
            "pids": self.pids,
        }


@dataclass(frozen=True)
class HostStats:
    cpus: Optional[int]
    loadavg: Optional[tuple[float, float, float]]
    memory: Optional[MemoryUsage]
    memory_total_bytes: Optional[int]
    memory_available_bytes: Optional[int]
    disk_path: Optional[str]
    disk_total_bytes: Optional[int]
    disk_used_bytes: Optional[int]
    disk_free_bytes: Optional[int]
    disk_used_percent: Optional[float]
    uptime_seconds: Optional[float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpus": self.cpus,
            "loadavg": list(self.loadavg) if self.loadavg is not None else None,
            "memory": {
                "total_bytes": self.memory_total_bytes,
                "available_bytes": self.memory_available_bytes,
                "used_bytes": self.memory.used_bytes if self.memory else None,
                "used_percent": self.memory.used_percent if self.memory else None,
            },
            "disk": {
                "path": self.disk_path,
                "total_bytes": self.disk_total_bytes,
                "used_bytes": self.disk_used_bytes,
                "free_bytes": self.disk_free_bytes,
                "used_percent": self.disk_used_percent,
            },
            "uptime_seconds": self.uptime_seconds,
        }


@dataclass(frozen=True)
class StatsSnapshot:
    host: HostStats
    containers: tuple[ContainerStats, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host.to_dict(),
            "containers": [c.to_dict() for c in self.containers],
        }
