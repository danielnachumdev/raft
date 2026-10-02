"""Shared host/snapshot fixtures for status tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock

from raft.adapters.docker.runtime import ContainerRuntimeRow
from raft.adapters.host import HostDisk, HostMemory, HostResources
from raft.services.ops.status.models import (
    AllocatedResources,
    ContainerStatus,
    HostStatus,
    IoPair,
    MemoryUsage,
    StatusSnapshot,
)


class StatusFixtures:
    @staticmethod
    def host() -> HostResources:
        return HostResources(
            cpus=4,
            loadavg=(0.1, 0.2, 0.3),
            memory=HostMemory(
                total_bytes=8 * 1024**3,
                available_bytes=4 * 1024**3,
                used_bytes=4 * 1024**3,
                used_percent=50.0,
            ),
            disk=HostDisk(
                path="/data",
                total_bytes=100 * 1024**3,
                used_bytes=40 * 1024**3,
                free_bytes=60 * 1024**3,
                used_percent=40.0,
            ),
            uptime_seconds=90061.0,
        )

    @staticmethod
    def empty_host_status() -> HostStatus:
        return HostStatus(
            hostname="test-host",
            cpus=1,
            loadavg=None,
            memory=None,
            memory_total_bytes=None,
            memory_available_bytes=None,
            disk_path=None,
            disk_total_bytes=None,
            disk_used_bytes=None,
            disk_free_bytes=None,
            disk_used_percent=None,
            uptime_seconds=None,
        )

    @staticmethod
    def allocated(
        cpus: str = "0.5",
        memory: str = "128M",
        res_cpus: str = "0.1",
        res_mem: str = "32M",
    ) -> AllocatedResources:
        return AllocatedResources(cpus, memory, res_cpus, res_mem)

    @classmethod
    def container(
        cls,
        service: str,
        *,
        role: str = "app",
        app: Optional[str] = None,
        group: Optional[str] = None,
        status: str = "running",
        uptime: Optional[float] = 1.0,
        cpu: Optional[float] = 1.0,
        mem_used: Optional[int] = 1024,
        mem_limit: Optional[int] = 2048,
        mem_pct: Optional[float] = 50.0,
        allocated: Optional[AllocatedResources] = None,
        pids: Optional[int] = 1,
    ) -> ContainerStatus:
        return ContainerStatus(
            service=service,
            role=role,
            app=app,
            group=group,
            status=status,
            uptime_seconds=uptime,
            cpu_percent=cpu,
            memory=MemoryUsage(mem_used, mem_limit, mem_pct),
            allocated=allocated or cls.allocated(),
            network=IoPair(None, None),
            block_io=IoPair(None, None),
            pids=pids,
        )

    @classmethod
    def snapshot(
        cls, *containers: ContainerStatus, host: Optional[HostStatus] = None
    ) -> StatusSnapshot:
        return StatusSnapshot(host=host or cls.empty_host_status(), containers=containers)

    @staticmethod
    def mock_containers_idle(status) -> MagicMock:
        gateway = MagicMock()
        gateway.collect.return_value = {}
        status._containers = gateway
        return gateway

    @staticmethod
    def mock_docker_idle(status) -> MagicMock:
        """Alias for older tests — mocks the container runtime gateway."""
        return StatusFixtures.mock_containers_idle(status)

    @staticmethod
    def started_iso(days: int = 1) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def runtime_row(
        cid: str,
        *,
        status: str = "running",
        health: str = "none",
        started: Optional[str] = None,
        memory_bytes: Optional[int] = 33554432,
        stats: Optional[dict] = None,
    ) -> ContainerRuntimeRow:
        return ContainerRuntimeRow(
            container_id=cid,
            status=status,
            health=health,
            started_at=started or StatusFixtures.started_iso(),
            memory_bytes=memory_bytes,
            stats=stats,
        )

    @classmethod
    def gate_router_stats_rows(cls) -> dict:
        return {
            "gatecid": {
                "CPUPerc": "0.5%",
                "MemUsage": "3.0MiB / 32MiB",
                "MemPerc": "4.7%",
                "NetIO": "1kB / 2kB",
                "BlockIO": "0B / 0B",
                "PIDs": "5",
            },
            "routercid": {
                "CPUPerc": "0.1%",
                "MemUsage": "2.0MiB / 32MiB",
                "MemPerc": "3.1%",
                "NetIO": "0B / 0B",
                "BlockIO": "1B / 2B",
                "PIDs": "2",
            },
        }

    @classmethod
    def wire_gate_router_running(cls, gateway: MagicMock) -> None:
        stats = cls.gate_router_stats_rows()
        gateway.collect.return_value = {
            "raft-gate": cls.runtime_row(
                "gatecid", memory_bytes=33554432, stats=stats["gatecid"]
            ),
            "raft-router": cls.runtime_row(
                "routercid", memory_bytes=0, stats=stats["routercid"]
            ),
        }
