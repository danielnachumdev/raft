"""Run ``raft redeploy <name>`` on the host from the always-on dashboard."""

from typing import Optional

from raft.core.core.models.app import App
from raft.core.core.models.stack import Stack
from raft.core.platform.adapters.docker import HostOneshot, HostOneshotGate
from raft.core.platform.adapters.shell import Shell


class HostServiceRedeploy:
    """Sync host oneshot for app / edge / controller redeploy (not dashboard).

    Always-on dashboard lacks a real passwd row for OpenSSH/git; host oneshot
    mounts operator ``HOME`` + ``/etc/passwd`` (same as GithubDeployHostGit).
    """

    _TIMEOUT = 1800.0

    def __init__(
        self,
        stack: Stack,
        *,
        shell: Optional[Shell] = None,
        oneshot: Optional[HostOneshot] = None,
        gate: Optional[HostOneshotGate] = None,
    ) -> None:
        self._stack = stack
        self._shell = shell or Shell(stack.root)
        self._oneshot = oneshot or HostOneshot(self._shell)
        self._gate = gate or HostOneshotGate()

    def run(self, compose_id: str, app: Optional[App]) -> None:
        """Ensure host oneshot preflight, then ``raft redeploy`` on the host."""
        self._gate.ensure()
        self._oneshot.run(
            self.argv(compose_id, app),
            timeout=self._TIMEOUT,
            with_docker=True,
        )

    def argv(self, compose_id: str, app: Optional[App]) -> list[str]:
        return ["raft", "redeploy", self.cli_name(compose_id, app)]

    def cli_name(self, compose_id: str, app: Optional[App]) -> str:
        if app is not None:
            return app.name
        return self._edge_cli_name(compose_id)

    def _edge_cli_name(self, compose_id: str) -> str:
        mapping = {
            self._stack.gate: "gate",
            self._stack.router: "router",
            self._stack.controller: "controller",
            self._stack.dashboard: "dashboard",
        }
        return mapping.get(compose_id, compose_id)
