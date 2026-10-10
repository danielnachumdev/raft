"""Shared dependencies for doctor check suites."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from raft.adapters import DockerStack, Shell
from raft.adapters.docker.compose_status import ComposeStatusTable
from raft.adapters.docker.runtime import ContainerRuntimeGateway, ContainerRuntimeRow
from raft.models.stack import Stack
from raft.ui.progress import TerminalProgress
from raft.auth import GitAuthManager


@dataclass(frozen=True)
class DoctorContext:
    stack: Stack
    shell: Shell
    auth: GitAuthManager
    docker: DockerStack
    on_progress: Optional[Callable[[str], None]] = None
    _compose_cache: Dict[str, ComposeStatusTable] = field(
        default_factory=dict, repr=False, compare=False
    )
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

    def compose_status(self) -> ComposeStatusTable:
        """Doctor-scoped batch compose status (filled once per doctor run)."""
        cached = self._compose_cache.get("table")
        if cached is None:
            cached = self.docker.compose_service_status()
            self._compose_cache["table"] = cached
        return cached

    def runtime_rows(self) -> Dict[str, ContainerRuntimeRow]:
        """Engine inspect/stats rows for core services (once per doctor run)."""
        cached = self._runtime_cache.get("rows")
        if cached is None:
            gateway = ContainerRuntimeGateway(self.shell)
            cached = gateway.collect(list(self.stack.core_services))
            self._runtime_cache["rows"] = cached
        return cached

    def running_services(self) -> list[str]:
        return self.compose_status().running_names(self.stack.core_services)

    def service_runtime(self, service: str) -> tuple[str, str]:
        """``(state, health)`` from the batched compose snapshot."""
        return self.compose_status().runtime(service)
