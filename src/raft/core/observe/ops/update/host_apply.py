"""Whether ``SelfUpdate`` can reinstall the host uv-tool CLI from this process."""

from __future__ import annotations

import os
import shutil
from typing import Optional

from raft.core.core.errors.cta import OperatorError

# Set only by always-on ``raft-dashboard`` Compose (see compose_yaml.py).
_DASHBOARD_APP_PORT_ENV = "RAFT_DASHBOARD_APP_PORT"

_DASHBOARD_BLOCK = (
    "Cannot apply raft update from the always-on dashboard container.\n"
    "The dashboard image has no host curl/uv tool env; ``install.sh`` would "
    "not update the host CLI (and may report a false success).\n"
    "Fix: on the host run `raft update`, then recreate the dashboard so the "
    "image rebuilds with the new install stamp "
    "(`raft dashboard disable` then `raft dashboard enable`)."
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

    def blocked_reason(self) -> Optional[str]:
        if self._in_dashboard_container():
            return _DASHBOARD_BLOCK
        if shutil.which("curl") is None:
            return _MISSING_CURL
        return None

    def ensure(self) -> None:
        reason = self.blocked_reason()
        if reason is not None:
            raise OperatorError(reason)

    @staticmethod
    def _in_dashboard_container() -> bool:
        return bool((os.environ.get(_DASHBOARD_APP_PORT_ENV) or "").strip())
