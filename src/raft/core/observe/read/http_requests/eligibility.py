"""Decide whether a Compose service gets HTTP request inspection."""

from dataclasses import dataclass
from typing import Optional, Set, Tuple

from raft.core.core.models.app import (
    CONTROLLER_COMPOSE_ID,
    DASHBOARD_COMPOSE_ID,
    GATE_COMPOSE_ID,
    ROUTER_COMPOSE_ID,
    App,
)
from raft.core.core.models.stack import Stack

_EDGE_IDS = frozenset(
    {GATE_COMPOSE_ID, ROUTER_COMPOSE_ID, CONTROLLER_COMPOSE_ID, DASHBOARD_COMPOSE_ID}
)
_EDGE_ALIASES = {
    "gate": GATE_COMPOSE_ID,
    "router": ROUTER_COMPOSE_ID,
    "controller": CONTROLLER_COMPOSE_ID,
    "dashboard": DASHBOARD_COMPOSE_ID,
}


@dataclass(frozen=True)
class HttpRequestsTarget:
    """Resolved Host-routed App for request inspection (or ineligible)."""

    compose_id: str
    eligible: bool
    reason: Optional[str] = None
    app: Optional[App] = None
    hosts: Tuple[str, ...] = ()
    unknown: bool = False

    @property
    def host_set(self) -> Set[str]:
        return {h.lower() for h in self.hosts}


class HttpRequestsEligibility:
    """Map serve/CLI names to Host-routed Apps (or an ineligible reason).

    Eligibility is manifest-only (``expose: http`` + ``publicHost``). Compose
    runtime — scaled-to-zero, stopped, or missing container — never denies
    inspection; gate ``access.log`` history is independent of the App process.
    """

    def __init__(self, stack: Stack) -> None:
        self.stack = stack

    def resolve(self, name: str) -> HttpRequestsTarget:
        key = name.strip()
        edge_id = _EDGE_ALIASES.get(key, key if key in _EDGE_IDS else None)
        if edge_id is not None:
            return self._denied(
                edge_id, "edge and control-plane services have no App Host traffic"
            )
        app = self._find_app(key)
        if app is None:
            return HttpRequestsTarget(
                compose_id=key,
                eligible=False,
                reason=f"unknown service '{key}'",
                unknown=True,
            )
        return self._for_app(app)

    def _for_app(self, app: App) -> HttpRequestsTarget:
        spec = self._load_spec(app)
        if spec is None:
            return self._denied(
                app.compose_id,
                "could not load App manifest for HTTP eligibility",
                app=app,
            )
        reason = self._ineligible_reason(app, spec)
        if reason:
            return self._denied(app.compose_id, reason, app=app)
        hosts = tuple(h.lower() for h in spec.server_names(app.public_host) if h.strip())
        return HttpRequestsTarget(
            compose_id=app.compose_id, eligible=True, app=app, hosts=hosts
        )

    def _load_spec(self, app: App):
        try:
            return self.stack.spec_for(app)
        except Exception:  # noqa: BLE001 — soft-fail bad registry for read path
            return None

    @staticmethod
    def _ineligible_reason(app: App, spec) -> Optional[str]:
        # Do not consult ScalingStore / Docker here — idle scale-to-zero and
        # stopped containers must still resolve as eligible for log history.
        if not spec.http_ports():
            return "HTTP request inspection requires at least one expose: http port"
        if not app.public_host.strip():
            return "HTTP request inspection requires publicHost"
        return None

    def _find_app(self, key: str) -> Optional[App]:
        for app in self.stack.apps:
            if app.name == key or app.compose_id == key:
                return app
        return None

    @staticmethod
    def _denied(
        compose_id: str, reason: str, *, app: Optional[App] = None
    ) -> HttpRequestsTarget:
        return HttpRequestsTarget(
            compose_id=compose_id, eligible=False, reason=reason, app=app
        )
