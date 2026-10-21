"""Whether ``SelfUpdate`` can reinstall the host uv-tool CLI from this process."""

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
    "Cannot apply raft update from the always-on dashboard: "
    "RAFT_HOST_HOME is unset or not an absolute path.\n"
    "Fix: on the host run `raft render`, then `raft redeploy dashboard` "
    "so Compose injects the operator home. Or run `raft update` on the host."
)

_MISSING_DOCKER_SOCK = (
    "Cannot apply raft update from the always-on dashboard: "
    "Docker socket is not available at /var/run/docker.sock.\n"
    "Fix: `raft redeploy dashboard` (docker.sock volume), or run "
    "`raft update` on the host."
)

_MISSING_DOCKER_CLI = (
    "Cannot apply raft update from the always-on dashboard: "
    "`docker` is not on PATH.\n"
    "Fix: `raft redeploy dashboard` (docker CLI is baked in), or run "
    "`raft update` on the host."
)

_MISSING_CURL = (
    "Cannot run raft update: `curl` is not on PATH.\n"
    "Fix: install curl, then retry `raft update` "
    "(or Settings → Update from a host `raft serve` process)."
)


class HostApplyGate:
    """Preflight for Settings / serve apply vs host ``raft update``."""

    def can_apply(self) -> bool:
        return self.blocked_reason() is None

    def uses_host_docker(self) -> bool:
        """Dashboard apply uses a host-targeted Docker one-shot."""
        return self._in_dashboard_container() and self.blocked_reason() is None

    def blocked_reason(self) -> Optional[str]:
        if self._in_dashboard_container():
            return self._dashboard_block()
        if shutil.which("curl") is None:
            return _MISSING_CURL
        return None

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

    @staticmethod
    def _in_dashboard_container() -> bool:
        return bool((os.environ.get(_DASHBOARD_APP_PORT_ENV) or "").strip())
