"""Shared dependencies for doctor check suites."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from raft.core.platform.adapters.docker.runtime import ContainerRuntimeGateway, ContainerRuntimeRow
from raft.core.platform.adapters.docker.stack import DockerStack
from raft.core.platform.adapters.shell import Shell
from raft.core.core.models.stack import Stack
from raft.core.core.ui.progress import TerminalProgress
from raft.core.platform.auth import GitAuthManager


@dataclass(frozen=True)
class DoctorContext:
    stack: Stack
    shell: Shell
    auth: GitAuthManager
    docker: DockerStack
    on_progress: Optional[Callable[[str], None]] = None
    _runtime_cache: Dict[str, Dict[str, ContainerRuntimeRow]] = field(
        default_factory=dict, repr=False, compare=False
    )

    def progress(self, label: str) -> None:
        if self.on_progress is not None:
            self.on_progress(label)
            return
        active = TerminalProgress.active()
        if active is not None:
            active.set_text(label)

    def runtime_rows(self) -> Dict[str, ContainerRuntimeRow]:
        """Labeled ``docker ps`` + inspect rows (once per doctor run, no stats)."""
        cached = self._runtime_cache.get("rows")
        if cached is None:
            cached = self._load_runtime_rows()
            self._runtime_cache["rows"] = cached
        return cached

    def _load_runtime_rows(self) -> Dict[str, ContainerRuntimeRow]:
        gateway = ContainerRuntimeGateway(self.shell)
        # State and health come from inspect. Skip ``docker stats`` (unused here).
        return gateway.collect(list(self.stack.core_services), include_stats=False)

    def running_services(self) -> list[str]:
        """Core services whose inspect status is ``running`` (not restarting)."""
        rows = self.runtime_rows()
        return [name for name in self.stack.core_services if _is_running(rows.get(name))]

    def service_runtime(self, service: str) -> tuple[str, str]:
        """``(state, health)`` from inspect. Absent containers are ``missing``."""
        row = self.runtime_rows().get(service)
        if row is None:
            return ("missing", "none")
        return (_engine_status(row), _engine_health(row))


def _is_running(row: Optional[ContainerRuntimeRow]) -> bool:
    return row is not None and row.status.strip().lower() == "running"


def _engine_status(row: ContainerRuntimeRow) -> str:
    return row.status.strip().lower()


def _engine_health(row: ContainerRuntimeRow) -> str:
    return row.health.strip().lower()
