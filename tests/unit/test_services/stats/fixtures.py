"""Shared host/snapshot fixtures for stats tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import MagicMock

from raft.adapters.host import HostDisk, HostMemory, HostResources
from raft.services.stats.models import (
    AllocatedResources,
    ContainerStats,
    HostStats,
    IoPair,
    MemoryUsage,
    StatsSnapshot,
)


class StatsFixtures:
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
    def empty_host_stats() -> HostStats:
        return HostStats(
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
    ) -> ContainerStats:
        return ContainerStats(
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
    def snapshot(cls, *containers: ContainerStats, host: Optional[HostStats] = None) -> StatsSnapshot:
        return StatsSnapshot(host=host or cls.empty_host_stats(), containers=containers)

    @staticmethod
    def mock_docker_idle(stats) -> MagicMock:
        docker = MagicMock()
        docker.try_service_container_id.return_value = None
        docker.containers_stats.return_value = {}
        stats.docker = docker
        return docker

    @staticmethod
    def started_iso(days: int = 1) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    @staticmethod
    def gate_router_stats_rows() -> dict:
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
    def wire_gate_router_running(cls, docker: MagicMock) -> None:
        docker.try_service_container_id.side_effect = lambda s: {
            "raft-gate": "gatecid",
            "raft-router": "routercid",
        }.get(s)
        docker.containers_stats.return_value = cls.gate_router_stats_rows()
        started = cls.started_iso()
        docker.container_inspect_runtime.side_effect = [
            {
                "status": "running",
                "started_at": started,
                "nano_cpus": 250000000,
                "memory_bytes": 33554432,
            },
            {
                "status": "running",
                "started_at": started,
                "nano_cpus": 250000000,
                "memory_bytes": 0,
            },
        ]
