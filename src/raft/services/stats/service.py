"""Collect point-in-time host + raft container resource stats."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ...adapters import DockerStack, Shell, collect_host_resources
from ...adapters.host import (
    HostResources,
    parse_docker_pair,
    parse_percent,
)
from ...errors import OperatorError
from ...models import Stack
from ...models.app import App
from ...models.stack import load_stack
from .models import (
    EDGE_CPUS_LIMIT,
    EDGE_CPUS_RESERVATION,
    EDGE_MEMORY_LIMIT,
    EDGE_MEMORY_RESERVATION,
    AllocatedResources,
    ContainerStats,
    HostStats,
    IoPair,
    MemoryUsage,
    StatsSnapshot,
)
from .report import write_live_report, write_report


def _edge_allocated() -> AllocatedResources:
    return AllocatedResources(
        cpus_limit=EDGE_CPUS_LIMIT,
        memory_limit=EDGE_MEMORY_LIMIT,
        cpus_reservation=EDGE_CPUS_RESERVATION,
        memory_reservation=EDGE_MEMORY_RESERVATION,
    )


def _app_allocated(stack: Stack, app: App) -> AllocatedResources:
    try:
        spec = stack.spec_for(app)
    except (OSError, ValueError, KeyError, OperatorError):
        return AllocatedResources(
            cpus_limit="0.50",
            memory_limit="128M",
            cpus_reservation="0.10",
            memory_reservation="32M",
        )
    return AllocatedResources(
        cpus_limit=spec.cpus_limit,
        memory_limit=spec.memory_limit,
        cpus_reservation=spec.cpus_reservation,
        memory_reservation=spec.memory_reservation,
    )


def _parse_started_at(raw: str) -> Optional[float]:
    text = (raw or "").strip()
    if not text or text.startswith("0001-01-01"):
        return None
    # Docker uses RFC3339 with trailing Z or offset.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        started = datetime.fromisoformat(text)
    except ValueError:
        return None
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max(0.0, (now - started).total_seconds())


def _pids(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def _host_stats(resources: HostResources) -> HostStats:
    mem = None
    total = available = None
    if resources.memory is not None:
        total = resources.memory.total_bytes
        available = resources.memory.available_bytes
        mem = MemoryUsage(
            used_bytes=resources.memory.used_bytes,
            limit_bytes=resources.memory.total_bytes,
            used_percent=resources.memory.used_percent,
        )
    disk = resources.disk
    return HostStats(
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


def _container_from_row(
    *,
    service: str,
    role: str,
    app: Optional[str],
    group: Optional[str],
    allocated: AllocatedResources,
    status: str,
    uptime_seconds: Optional[float],
    stats_row: Optional[dict[str, Any]],
    inspect_memory: Optional[int],
) -> ContainerStats:
    cpu = mem_pct = None
    used = limit = None
    net = IoPair(None, None)
    block = IoPair(None, None)
    pids = None
    if stats_row:
        cpu = parse_percent(str(stats_row.get("CPUPerc", "")))
        mem_pct = parse_percent(str(stats_row.get("MemPerc", "")))
        used, limit = parse_docker_pair(str(stats_row.get("MemUsage", "")))
        rx, tx = parse_docker_pair(str(stats_row.get("NetIO", "")))
        rd, wr = parse_docker_pair(str(stats_row.get("BlockIO", "")))
        net = IoPair(rx, tx)
        block = IoPair(rd, wr)
        pids = _pids(stats_row.get("PIDs"))
    if limit is None and inspect_memory and inspect_memory > 0:
        limit = inspect_memory
    return ContainerStats(
        service=service,
        role=role,
        app=app,
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


class Stats:
    """Point-in-time resource snapshot for operators (`raft stats`)."""

    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.sh = Shell(stack.root)
        self.docker = DockerStack(stack, self.sh)

    def _reload_stack(self) -> None:
        """Re-read applied apps so live mode picks up apply/delete/start changes."""
        self.stack = load_stack(self.stack.root)
        self.docker = DockerStack(self.stack, self.sh)

    def collect(self, *, refresh_apps: bool = False) -> StatsSnapshot:
        if refresh_apps:
            self._reload_stack()
        host = _host_stats(collect_host_resources(disk_path=self.stack.root))
        targets: list[tuple[str, str, Optional[str], Optional[str], AllocatedResources]] = [
            (self.stack.gate, "gate", None, None, _edge_allocated()),
            (self.stack.router, "router", None, None, _edge_allocated()),
        ]
        for app in self.stack.apps:
            targets.append(
                (
                    app.compose_id,
                    "app",
                    app.name,
                    app.group,
                    _app_allocated(self.stack, app),
                )
            )

        id_by_service: dict[str, str] = {}
        for service, *_rest in targets:
            cid = self.docker.try_service_container_id(service)
            if cid:
                id_by_service[service] = cid

        stats_by_id = self.docker.containers_stats(list(id_by_service.values()))

        containers: list[ContainerStats] = []
        for service, role, app_name, group, allocated in targets:
            cid = id_by_service.get(service)
            if not cid:
                containers.append(
                    _container_from_row(
                        service=service,
                        role=role,
                        app=app_name,
                        group=group,
                        allocated=allocated,
                        status="not running",
                        uptime_seconds=None,
                        stats_row=None,
                        inspect_memory=None,
                    )
                )
                continue
            runtime = self.docker.container_inspect_runtime(cid) or {}
            status = str(runtime.get("status") or "unknown")
            uptime = _parse_started_at(str(runtime.get("started_at") or ""))
            inspect_mem = runtime.get("memory_bytes")
            mem_limit = inspect_mem if isinstance(inspect_mem, int) else None
            containers.append(
                _container_from_row(
                    service=service,
                    role=role,
                    app=app_name,
                    group=group,
                    allocated=allocated,
                    status=status,
                    uptime_seconds=uptime,
                    stats_row=stats_by_id.get(cid),
                    inspect_memory=mem_limit,
                )
            )
        return StatsSnapshot(host=host, containers=tuple(containers))

    def report(self, *, as_json: bool = False, live: bool = False) -> int:
        if as_json and live:
            raise OperatorError("raft stats: --json and --live cannot be combined")
        if live:
            return write_live_report(lambda: self.collect(refresh_apps=True))
        return write_report(self.collect(), as_json=as_json)
