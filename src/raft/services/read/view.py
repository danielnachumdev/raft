"""Map a StatusSnapshot into template/API-friendly rows."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Tuple

from ...models.app import display_service_label
from ..ops.status.formatters import StatusFormatters
from ..ops.status.models import ContainerStatus, StatusSnapshot
from .depends import ServeDependsMap
from .external_urls import ExternalUrlBuilder

_CONTROL_ROLES = frozenset({"gate", "router", "controller"})


@dataclass(frozen=True)
class ServeRow:
    service: str
    name: str
    role: str
    group: str
    status: str
    cpu: str
    memory: str
    started: str
    uptime: str
    external_urls: Tuple[str, ...] = field(default_factory=tuple)
    depends_on: Tuple[str, ...] = field(default_factory=tuple)


class ServeSnapshotView:
    """Split control-plane vs apps; format columns for serve tables / API."""

    def __init__(
        self,
        snapshot: StatusSnapshot,
        urls: Optional[ExternalUrlBuilder] = None,
        depends: Optional[ServeDependsMap] = None,
    ) -> None:
        self.snapshot = snapshot
        self._urls = urls
        self._depends = depends

    def control_plane(self) -> Tuple[ServeRow, ...]:
        return tuple(self._row(c) for c in self.snapshot.containers if c.role in _CONTROL_ROLES)

    def apps(self) -> Tuple[ServeRow, ...]:
        return tuple(self._row(c) for c in self.snapshot.containers if c.role == "app")

    def to_payload(self) -> Dict[str, Any]:
        """Presentation lists for serve tables (StatusRead merges onto snapshot)."""
        return {
            "host": self.snapshot.host.to_dict(),
            "control_plane": [self._row_dict(r) for r in self.control_plane()],
            "apps": [self._row_dict(r) for r in self.apps()],
        }

    def service_detail(self, name: str) -> Optional[Dict[str, Any]]:
        """Full status for one Compose service id, or None if unknown."""
        container = self._find_container(name)
        if container is None:
            return None
        return {
            "host": self.snapshot.host.to_dict(),
            "container": container.to_dict(),
            "presentation": self._row_dict(self._row(container)),
        }

    @staticmethod
    def _row_dict(row: ServeRow) -> Dict[str, Any]:
        data = asdict(row)
        data["external_urls"] = list(row.external_urls)
        data["depends_on"] = list(row.depends_on)
        return data

    def _find_container(self, name: str) -> Optional[ContainerStatus]:
        for container in self.snapshot.containers:
            if container.service == name:
                return container
        return None

    def _row(self, container: ContainerStatus) -> ServeRow:
        mem = container.memory
        used = StatusFormatters.bytes(mem.used_bytes)
        limit = StatusFormatters.bytes(mem.limit_bytes)
        return ServeRow(
            service=container.service,
            name=display_service_label(container.service, container.group),
            role=container.role,
            group=container.group or "-",
            status=container.status,
            cpu=StatusFormatters.percent(container.cpu_percent),
            memory=f"{used} / {limit}",
            started=StatusFormatters.started(container.uptime_seconds),
            uptime=StatusFormatters.uptime(container.uptime_seconds),
            external_urls=self._external_urls(container),
            depends_on=self._depends_on(container),
        )

    def _external_urls(self, container: ContainerStatus) -> Tuple[str, ...]:
        if self._urls is None:
            return ()
        return self._urls.urls_for(service=container.service, role=container.role)

    def _depends_on(self, container: ContainerStatus) -> Tuple[str, ...]:
        if self._depends is None or container.role != "app":
            return ()
        return self._depends.for_service(container.service)
