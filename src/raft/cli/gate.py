"""CLI for deliberate gate container recreate (published edge ports)."""

from __future__ import annotations

from . import deps
from ..models.stack import Stack


class GateCLI:
    """gate — recreate the public edge container when published ports change."""

    def __init__(self, stack: Stack) -> None:
        self._stack = stack

    def recreate(self) -> None:
        """Recreate gate to pick up settings edge: ports (brief downtime)."""
        deps.Orchestrator(self._stack).recreate_gate()
