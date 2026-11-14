"""Collect point-in-time host + raft container resource usage."""

from typing import Optional, Tuple

from raft.core.platform.adapters.docker.runtime import ContainerRuntimeGateway
from raft.core.platform.adapters.host import HostGateway, HostResources
from raft.core.platform.adapters.shell import Shell
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import EDGE_GROUP
from raft.core.core.models.stack import Stack
from .allocated import StatusAllocated
from .container_rows import StatusContainerRows
from .models import (
    AllocatedResources,
    HostStatus,
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

    def collect(
        self, *, refresh_apps: bool = False, include_stats: bool = True
    ) -> StatusSnapshot:
        """Live host + container snapshot.

        ``include_stats=False`` skips Engine ``docker stats``. Serve and the
        default ``raft status`` then overlay CPU/mem from controller JSONL.
        ``raft status --live`` keeps a live stats snapshot.
        """
        if refresh_apps:
            self._reload_stack()
        targets = self._targets()
        runtime = self._containers.collect(
            [t[0] for t in targets], include_stats=include_stats
        )
        rows = StatusContainerRows(self.stack.root)
        containers = tuple(
            rows.build(service, role, app_name, group, allocated, runtime)
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
        allocated = {
            self.stack.gate: edge,
            self.stack.router: edge,
            self.stack.controller: StatusAllocated.controller(),
            self.stack.dashboard: StatusAllocated.controller(),
        }
        roles = {
            self.stack.gate: "gate",
            self.stack.router: "router",
            self.stack.controller: "controller",
            self.stack.dashboard: "dashboard",
        }
        return [
            (name, roles[name], None, EDGE_GROUP, allocated[name])
            for name in self.stack.control_plane_services
        ]

    @staticmethod
    def _host_status(gateway: HostGateway) -> HostStatus:
        resources = gateway.resources()
        mem, total, available = Status._host_memory(resources)
        disk = resources.disk
        return HostStatus(
            hostname=gateway.hostname(),
            fqdn=gateway.fqdn(),
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

    def sampled_snapshot(self, *, refresh_apps: bool = False) -> StatusSnapshot:
        """Lite runtime plus a fresh controller sample (no ``docker stats``)."""
        # Local import: read/__init__ imports Status, so a module-level import cycles.
        from raft.core.observe.read.status_resources_overlay import StatusResourcesOverlay

        snap = self.collect(refresh_apps=refresh_apps, include_stats=False)
        return StatusResourcesOverlay(self.stack.root).apply(snap)

    def report(self, *, as_json: bool = False, live: bool = False) -> int:
        if as_json and live:
            raise OperatorError("raft status: --json and --live cannot be combined")
        writer = StatusReportWriter()
        if live:
            return writer.write_live(
                lambda: self.collect(refresh_apps=True, include_stats=True)
            )
        return writer.write(self.sampled_snapshot(), as_json=as_json)
