"""Shared dependencies for doctor check suites."""

from __future__ import annotations

from dataclasses import dataclass

from ....adapters import DockerStack, Shell
from ....models import Stack
from ...auth import GitAuthManager


@dataclass(frozen=True)
class DoctorContext:
    stack: Stack
    shell: Shell
    auth: GitAuthManager
    docker: DockerStack
