"""Collect point-in-time host + raft container resource usage."""

from __future__ import annotations

from typing import Any, Optional, Tuple

from ....adapters import Shell
from ....adapters.docker.crash_loop import CrashLoopDetector
from ....adapters.docker.runtime import ContainerRuntimeGateway, ContainerRuntimeRow
from ....adapters.host import DockerStatsText, HostGateway, HostResources
from ....errors.cta import OperatorError
from ....models.app import EDGE_GROUP
from ....models.stack import Stack
from ....models.state.scaling_store import ScalingStore
from .allocated import StatusAllocated
from .formatters import StatusFormatters
from .models import (
    STATUS_NOT_RUNNING,
    STATUS_SCALED_TO_ZERO,
    AllocatedResources,
    ContainerStatus,
    HostStatus,
    IoPair,
    MemoryUsage,
    StatusSnapshot,
)
from .report import StatusReportWriter

_Target = Tuple[str, str, Optional[str], Optional[str], AllocatedResources]


class Status:
    """Point-in-time resource snapshot for operators (`raft status`)."""

    def __init__(
        self,
        stack: Stack,
        *,
        host: Optional[HostGateway] = None,
        containers: Optional[ContainerRuntimeGateway] = None,
    ) -> None:
        self.stack = stack
        self.sh = Shell(stack.root)
        self._host = host or HostGateway(disk_path=stack.root)
        self._containers = containers or ContainerRuntimeGateway(self.sh)

    def _reload_stack(self) -> None:
        """Re-read applied apps without ``ensure_raft_home`` / template sync."""
        self.stack = Stack.load_apps(self.stack.root)
        self.sh = Shell(self.stack.root)
        self._host = HostGateway(disk_path=self.stack.root)
        self._containers = ContainerRuntimeGateway(self.sh)

    def collect(self, *, refresh_apps: bool = False) -> StatusSnapshot:
        if refresh_apps:
            self._reload_stack()
        targets = self._targets()
        runtime = self._containers.collect([t[0] for t in targets])
        containers = tuple(
            self._one_container(service, role, app_name, group, allocated, runtime)
            for service, role, app_name, group, allocated in targets
        )
        return StatusSnapshot(host=self._host_status(self._host), containers=containers)

    def _targets(self) -> list[_Target]:
        targets = self._edge_targets()
        for app in self.stack.apps:
            targets.append(
                (
                    app.compose_id,
                    "app",
                    app.name,
                    app.group,
                    StatusAllocated.app(self.stack, app),
                )
            )
        return targets

    def _edge_targets(self) -> list[_Target]:
        edge = StatusAllocated.edge()
        return [
            (self.stack.gate, "gate", None, EDGE_GROUP, edge),
            (self.stack.router, "router", None, EDGE_GROUP, edge),
            (
                self.stack.controller,
                "controller",
                None,
                EDGE_GROUP,
                StatusAllocated.controller(),
            ),
        ]

    def _one_container(
        self,
        service: str,
        role: str,
        app_name: Optional[str],
        group: Optional[str],
        allocated: AllocatedResources,
        runtime: dict[str, ContainerRuntimeRow],
    ) -> ContainerStatus:
        row = runtime.get(service)
        if row is None:
            return self._absent_container(service, role, app_name, group, allocated)
        return self._present_container(service, role, app_name, group, allocated, row)

    def _absent_container(
        self,
        service: str,
        role: str,
        app_name: Optional[str],
        group: Optional[str],
        allocated: AllocatedResources,
    ) -> ContainerStatus:
        return self._container_row(
            service,
            role,
            app_name,
            group,
            allocated,
            status=self._absent_status(app_name),
            uptime_seconds=None,
            stats_row=None,
            inspect_memory=None,
        )

    def _absent_status(self, app_name: Optional[str]) -> str:
        if app_name and ScalingStore(self.stack.root).is_scaled_to_zero(app_name):
            return STATUS_SCALED_TO_ZERO
        return STATUS_NOT_RUNNING

    def _present_container(
        self,
        service: str,
        role: str,
        app_name: Optional[str],
        group: Optional[str],
        allocated: AllocatedResources,
        row: ContainerRuntimeRow,
    ) -> ContainerStatus:
        uptime = self._parse_started_at(row.started_at)
        return self._container_row(
            service,
            role,
            app_name,
            group,
            allocated,
            status=StatusFormatters.container_status(
                row.status,
                row.health,
                restart_count=row.restart_count,
                uptime_seconds=uptime,
                oom_killed=row.oom_killed,
            ),
            uptime_seconds=uptime,
            stats_row=row.stats,
            inspect_memory=row.memory_bytes,
        )

    @classmethod
    def _container_row(
        cls,
        service,
        role,
        app_name,
        group,
        allocated,
        *,
        status: str,
        uptime_seconds: Optional[float],
        stats_row: Optional[dict[str, Any]],
        inspect_memory: Optional[int],
    ) -> ContainerStatus:
        cpu, mem_pct, used, limit, net, block, pids = cls._row_metrics(stats_row)
        if limit is None and inspect_memory and inspect_memory > 0:
            limit = inspect_memory
        return ContainerStatus(
            service=service,
            role=role,
            app=app_name,
            group=group,
            status=status,
            uptime_seconds=uptime_seconds,
            cpu_percent=cpu,
            memory=MemoryUsage(used_bytes=used, limit_bytes=limit, used_percent=mem_pct),
            allocated=allocated,
            network=net,
            block_io=block,
            pids=pids,
        )

    @staticmethod
    def _row_metrics(
        stats_row: Optional[dict[str, Any]],
    ) -> tuple[
        Optional[float],
        Optional[float],
        Optional[int],
        Optional[int],
        IoPair,
        IoPair,
        Optional[int],
    ]:
        if not stats_row:
            empty = IoPair(None, None)
            return None, None, None, None, empty, empty, None
        used, limit = DockerStatsText.parse_pair(str(stats_row.get("MemUsage", "")))
        rx, tx = DockerStatsText.parse_pair(str(stats_row.get("NetIO", "")))
        rd, wr = DockerStatsText.parse_pair(str(stats_row.get("BlockIO", "")))
        return (
            DockerStatsText.parse_percent(str(stats_row.get("CPUPerc", ""))),
            DockerStatsText.parse_percent(str(stats_row.get("MemPerc", ""))),
            used,
            limit,
            IoPair(rx, tx),
            IoPair(rd, wr),
            Status._pids(stats_row.get("PIDs")),
        )

    @staticmethod
    def _pids(raw: Any) -> Optional[int]:
        if raw is None:
            return None
        try:
            return int(str(raw).strip())
        except ValueError:
            return None

    @staticmethod
    def _parse_started_at(raw: str) -> Optional[float]:
        return CrashLoopDetector.uptime_seconds(raw)

    @staticmethod
    def _host_status(gateway: HostGateway) -> HostStatus:
        resources = gateway.resources()
        mem, total, available = Status._host_memory(resources)
        disk = resources.disk
        return HostStatus(
            hostname=gateway.hostname(),
            cpus=resources.cpus,
            loadavg=resources.loadavg,
            memory=mem,
            memory_total_bytes=total,
            memory_available_bytes=available,
            disk_path=disk.path if disk else None,
            disk_total_bytes=disk.total_bytes if disk else None,
            disk_used_bytes=disk.used_bytes if disk else None,
            disk_free_bytes=disk.free_bytes if disk else None,
            disk_used_percent=disk.used_percent if disk else None,
            uptime_seconds=resources.uptime_seconds,
        )

    @staticmethod
    def _host_memory(
        resources: HostResources,
    ) -> tuple[Optional[MemoryUsage], Optional[int], Optional[int]]:
        if resources.memory is None:
            return None, None, None
        mem = MemoryUsage(
            used_bytes=resources.memory.used_bytes,
            limit_bytes=resources.memory.total_bytes,
            used_percent=resources.memory.used_percent,
        )
        return mem, resources.memory.total_bytes, resources.memory.available_bytes

    def report(self, *, as_json: bool = False, live: bool = False) -> int:
        if as_json and live:
            raise OperatorError("raft status: --json and --live cannot be combined")
        writer = StatusReportWriter()
        if live:
            return writer.write_live(lambda: self.collect(refresh_apps=True))
        return writer.write(self.collect(), as_json=as_json)
