"""Map a StatusSnapshot into template-friendly rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from ...models import display_service_label
from ..ops.status.formatters import StatusFormatters
from ..ops.status.models import ContainerStatus, StatusSnapshot

_CONTROL_ROLES = frozenset({"gate", "router", "controller"})


@dataclass(frozen=True)
class ServeRow:
    name: str
    role: str
    group: str
    status: str
    cpu: str
    memory: str
    uptime: str


class ServeSnapshotView:
    """Split control-plane vs apps and format columns for SSR."""

    def __init__(self, snapshot: StatusSnapshot) -> None:
        self.snapshot = snapshot

    def control_plane(self) -> Tuple[ServeRow, ...]:
        return tuple(self._row(c) for c in self.snapshot.containers if c.role in _CONTROL_ROLES)

    def apps(self) -> Tuple[ServeRow, ...]:
        return tuple(self._row(c) for c in self.snapshot.containers if c.role == "app")

    def _row(self, container: ContainerStatus) -> ServeRow:
        mem = container.memory
        used = StatusFormatters.bytes(mem.used_bytes)
        limit = StatusFormatters.bytes(mem.limit_bytes)
        return ServeRow(
            name=display_service_label(container.service, container.group),
            role=container.role,
            group=container.group or "-",
            status=container.status,
            cpu=StatusFormatters.percent(container.cpu_percent),
            memory=f"{used} / {limit}",
            uptime=StatusFormatters.uptime(container.uptime_seconds),
        )
