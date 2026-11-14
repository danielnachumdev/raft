"""Detach ``raft redeploy <name>`` on the host from the always-on dashboard."""

from typing import Any, Dict, Optional

from raft.core.core.models.app import App
from raft.core.core.models.stack import Stack
from raft.core.platform.adapters.docker import (
    HostOneshotFlight,
    HostOneshotGate,
    HostOneshotStart,
)
from raft.core.platform.adapters.shell import Shell


class HostServiceRedeploy:
    """Detached host oneshot for app / edge / controller redeploy (not dashboard).

    Always-on dashboard lacks a real passwd row for OpenSSH/git; host oneshot
    mounts operator ``HOME`` + ``/etc/passwd`` (same as GithubDeployHostGit).

    Sync ``run`` blocked the serve HTTP request past CDN/proxy timeouts, so the
    UI failed while the rebuild continued. Detach + coalesce like dashboard
    self-redeploy; SPA polls until the service is running again.
    """

    def __init__(
        self,
        stack: Stack,
        *,
        shell: Optional[Shell] = None,
        gate: Optional[HostOneshotGate] = None,
        flight: Optional[HostOneshotFlight] = None,
    ) -> None:
        self._stack = stack
        self._shell = shell or Shell(stack.root)
        self._gate = gate or HostOneshotGate()
        self._flight = flight

    def start(self, compose_id: str, app: Optional[App]) -> Dict[str, Any]:
        """Enqueue detached host ``raft redeploy``; coalesce concurrent clicks."""
        self._gate.ensure()
        name = self.cli_name(compose_id, app)
        started = self._flight_for(name).start(
            self.argv(compose_id, app), with_docker=True
        )
        return self.payload(compose_id, started)

    def argv(self, compose_id: str, app: Optional[App]) -> list[str]:
        return ["raft", "redeploy", self.cli_name(compose_id, app)]

    def cli_name(self, compose_id: str, app: Optional[App]) -> str:
        if app is not None:
            return app.name
        return self._edge_cli_name(compose_id)

    def _flight_for(self, cli_name: str) -> HostOneshotFlight:
        if self._flight is not None:
            return self._flight
        return HostOneshotFlight(
            self._stack.root,
            self.flight_kind(cli_name),
            shell=self._shell,
        )

    @staticmethod
    def flight_kind(cli_name: str) -> str:
        return f"redeploy-{cli_name}"

    @staticmethod
    def payload(compose_id: str, started: HostOneshotStart) -> Dict[str, Any]:
        return {
            "ok": True,
            "action": "redeploy",
            "service": compose_id,
            "started": True,
            "job_id": started.job_id,
            "coalesced": started.coalesced,
        }

    def _edge_cli_name(self, compose_id: str) -> str:
        mapping = {
            self._stack.gate: "gate",
            self._stack.router: "router",
            self._stack.controller: "controller",
            self._stack.dashboard: "dashboard",
        }
        return mapping.get(compose_id, compose_id)
