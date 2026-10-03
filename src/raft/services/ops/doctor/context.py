"""Shared dependencies for doctor check suites."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from ....adapters import DockerStack, Shell
from ....adapters.docker.compose_status import ComposeStatusTable
from ....models import Stack
from ....ui.progress import TerminalProgress
from ...auth import GitAuthManager


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

    def running_services(self) -> list[str]:
        return self.compose_status().running_names(self.stack.core_services)

    def service_runtime(self, service: str) -> tuple[str, str]:
        """``(state, health)`` from the batched compose snapshot."""
        return self.compose_status().runtime(service)
