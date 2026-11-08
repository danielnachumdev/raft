"""Dashboard redeploy: host oneshot start / join helpers for ServiceActions."""

from typing import Any, Dict, Optional

from raft.core.core.models.stack import Stack
from raft.core.core.ui import OperatorSay
from raft.core.platform.adapters.docker import (
    HostOneshotFlight,
    HostOneshotGate,
    HostOneshotStart,
)
from raft.core.platform.adapters.shell import Shell


class DashboardRedeploy:
    """Start or join a dashboard stamp rebuild (UI oneshot vs host CLI)."""

    def __init__(self, stack: Stack, *, shell: Optional[Shell] = None) -> None:
        self.stack = stack
        self._shell = shell or Shell(stack.root)

    def flight(self) -> HostOneshotFlight:
        return HostOneshotFlight(
            self.stack.root,
            HostOneshotFlight.KIND_DASHBOARD_REDEPLOY,
            shell=self._shell,
        )

    def start_oneshot(self, compose_id: str, gate: HostOneshotGate) -> Dict[str, Any]:
        """Detach host ``raft redeploy dashboard`` so the dashboard process can die."""
        gate.ensure()
        started = self.flight().start(
            ["raft", "redeploy", "dashboard"], with_docker=True
        )
        return self.payload(compose_id, started)

    def join_oneshot(self, compose_id: str) -> Optional[Dict[str, Any]]:
        """Wait for an in-flight UI oneshot instead of queueing a second rebuild."""
        flight = self.flight()
        job_id = flight.peek_alive()
        if job_id is None:
            return None
        OperatorSay.say(
            f"dashboard redeploy already in progress; waiting for job "
            f"{job_id[:12]}…",
            style="warn",
        )
        started = flight.join_alive(job_id)
        if started is None:
            return None
        return self.payload(compose_id, started)

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
