"""Resolve operator-facing names to Compose service ids for ``raft logs``."""

from __future__ import annotations

from ....errors.domain import unknown_logs_target
from ....models.app import (
    CONTROLLER_COMPOSE_ID,
    GATE_COMPOSE_ID,
    ROUTER_COMPOSE_ID,
)
from ....models.stack import Stack

_EDGE_ALIASES = {
    "gate": GATE_COMPOSE_ID,
    "router": ROUTER_COMPOSE_ID,
    "controller": CONTROLLER_COMPOSE_ID,
    GATE_COMPOSE_ID: GATE_COMPOSE_ID,
    ROUTER_COMPOSE_ID: ROUTER_COMPOSE_ID,
    CONTROLLER_COMPOSE_ID: CONTROLLER_COMPOSE_ID,
}


class LogsTargets:
    """Map ``gate`` / app names / compose ids to Compose service keys."""

    def __init__(self, stack: Stack) -> None:
        self.stack = stack

    def resolve(self, *names: str) -> tuple[str, ...]:
        """Resolve zero-or-more operator names; empty means all core services."""
        stripped = [n.strip() for n in names if n and n.strip()]
        if not stripped:
            return tuple(self.stack.core_services)
        return tuple(self._one(name) for name in stripped)

    def known_labels(self) -> str:
        """Comma-separated operator-facing labels for error CTAs."""
        labels = ["gate", "router", "controller", *(a.name for a in self.stack.apps)]
        return ", ".join(labels) if labels else "(none)"

    def _one(self, name: str) -> str:
        edge = _EDGE_ALIASES.get(name)
        if edge is not None:
            return edge
        for app in self.stack.apps:
            if app.name == name or app.compose_id == name:
                return app.compose_id
        raise unknown_logs_target(name, self.known_labels())
