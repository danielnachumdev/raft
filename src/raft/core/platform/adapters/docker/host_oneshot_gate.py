"""Preflight for host Docker one-shots from the always-on dashboard."""

from __future__ import annotations

import os
import shutil
from typing import Optional

from raft.core.core.errors.cta import OperatorError

# Set only by always-on ``raft-dashboard`` Compose (see compose_yaml.py).
_DASHBOARD_APP_PORT_ENV = "RAFT_DASHBOARD_APP_PORT"
_HOST_HOME_ENV = "RAFT_HOST_HOME"
_DOCKER_SOCK = "/var/run/docker.sock"

_MISSING_HOST_HOME = (
    "Cannot run a host one-shot from the always-on dashboard: "
    "RAFT_HOST_HOME is unset or not an absolute path.\n"
    "Fix: on the host run `raft render`, then `raft redeploy dashboard` "
    "so Compose injects the operator home. Or run the command on the host "
    "(`raft update` / `raft redeploy dashboard`)."
)

_MISSING_DOCKER_SOCK = (
    "Cannot run a host one-shot from the always-on dashboard: "
    "Docker socket is not available at /var/run/docker.sock.\n"
    "Fix: `raft redeploy dashboard` (docker.sock volume), or run "
    "the command on the host (`raft update` / `raft redeploy dashboard`)."
)

_MISSING_DOCKER_CLI = (
    "Cannot run a host one-shot from the always-on dashboard: "
    "`docker` is not on PATH.\n"
    "Fix: `raft redeploy dashboard` (docker CLI is baked in), or run "
    "the command on the host (`raft update` / `raft redeploy dashboard`)."
)


class HostOneshotGate:
    """Shared HOME + docker.sock + docker CLI checks for dashboard one-shots."""

    def in_dashboard(self) -> bool:
        return bool((os.environ.get(_DASHBOARD_APP_PORT_ENV) or "").strip())

    def can_run(self) -> bool:
        return self.blocked_reason() is None

    def blocked_reason(self) -> Optional[str]:
        if not self.in_dashboard():
            return None
        return self._dashboard_block()

    def ensure(self) -> None:
        reason = self.blocked_reason()
        if reason is not None:
            raise OperatorError(reason)

    def _dashboard_block(self) -> Optional[str]:
        home = (os.environ.get(_HOST_HOME_ENV) or "").strip()
        if not home or not os.path.isabs(home):
            return _MISSING_HOST_HOME
        if not os.path.exists(_DOCKER_SOCK):
            return _MISSING_DOCKER_SOCK
        if shutil.which("docker") is None:
            return _MISSING_DOCKER_CLI
        return None
