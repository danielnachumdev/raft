"""Shared dependencies for doctor check suites."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ....adapters import DockerStack, Shell
from ....models import Stack
from ...auth import GitAuthManager


@dataclass(frozen=True)
class DoctorContext:
    stack: Stack
    shell: Shell
    auth: GitAuthManager
    docker: DockerStack
    on_progress: Optional[Callable[[str], None]] = None

    def progress(self, label: str) -> None:
        if self.on_progress is not None:
            self.on_progress(label)
