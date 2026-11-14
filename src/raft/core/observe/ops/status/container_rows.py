"""Build ``ContainerStatus`` rows from runtime / absent / redeploying state."""

from pathlib import Path
from typing import Any, Optional

from raft.core.platform.adapters.docker.crash_loop import CrashLoopDetector
from raft.core.platform.adapters.docker.runtime import ContainerRuntimeRow
from raft.core.platform.adapters.host import DockerStatsText
from raft.core.core.models.state.redeploying_store import RedeployingStore
from .absent import AbsentStatus
from .formatters import StatusFormatters
from .models import (
    STATUS_REDEPLOYING,
    AllocatedResources,
    ContainerStatus,
    IoPair,
    MemoryUsage,
)


class StatusContainerRows:
    """Map Compose runtime (or its absence) to one status-table row."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def build(
        self,
        service: str,
        role: str,
        app_name: Optional[str],
        group: Optional[str],
        allocated: AllocatedResources,
        runtime: dict[str, ContainerRuntimeRow],
    ) -> ContainerStatus:
        if app_name and RedeployingStore(self._root).is_redeploying(app_name):
            return self._redeploying(
                service, role, app_name, group, allocated, runtime.get(service)
            )
        row = runtime.get(service)
        if row is None:
            return self._absent(service, role, app_name, group, allocated)
        return self._present(service, role, app_name, group, allocated, row)

    def _redeploying(
        self,
        service: str,
        role: str,
        app_name: Optional[str],
        group: Optional[str],
        allocated: AllocatedResources,
        row: Optional[ContainerRuntimeRow],
    ) -> ContainerStatus:
        uptime = self._uptime(row.started_at) if row is not None else None
        stats = row.stats if row is not None else None
        mem = row.memory_bytes if row is not None else None
        return self._row(
            service,
            role,
            app_name,
            group,
            allocated,
            status=STATUS_REDEPLOYING,
            uptime_seconds=uptime,
            stats_row=stats,
            inspect_memory=mem,
        )

    def _absent(
        self,
        service: str,
        role: str,
        app_name: Optional[str],
        group: Optional[str],
        allocated: AllocatedResources,
    ) -> ContainerStatus:
        return self._row(
            service,
            role,
            app_name,
            group,
            allocated,
            status=AbsentStatus.for_app(self._root, app_name),
            uptime_seconds=None,
            stats_row=None,
            inspect_memory=None,
        )

    def _present(
        self,
        service: str,
        role: str,
        app_name: Optional[str],
        group: Optional[str],
        allocated: AllocatedResources,
        row: ContainerRuntimeRow,
    ) -> ContainerStatus:
        uptime = self._uptime(row.started_at)
        return self._row(
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
    def _row(
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
        cpu, mem_pct, used, limit, net, block, pids = cls._metrics(stats_row)
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
    def _metrics(
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
            StatusContainerRows._pids(stats_row.get("PIDs")),
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
    def _uptime(raw: str) -> Optional[float]:
        return CrashLoopDetector.uptime_seconds(raw)
