"""Whether ``SelfUpdate`` can reinstall the host uv-tool CLI from this process."""

from __future__ import annotations

import shutil
from typing import Optional

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.adapters.docker import HostOneshotGate

_MISSING_CURL = (
    "Cannot run raft update: `curl` is not on PATH.\n"
    "Fix: install curl, then retry `raft update` "
    "(or Settings → Update from a host `raft serve` process)."
)


class HostApplyGate:
    """Preflight for Settings / serve apply vs host ``raft update``."""

    def __init__(self, oneshot_gate: Optional[HostOneshotGate] = None) -> None:
        self._oneshot = oneshot_gate or HostOneshotGate()

    def can_apply(self) -> bool:
        return self.blocked_reason() is None

    def uses_host_docker(self) -> bool:
        """Dashboard apply uses a host-targeted Docker one-shot."""
        return self._oneshot.in_dashboard() and self._oneshot.can_run()

    def blocked_reason(self) -> Optional[str]:
        if self._oneshot.in_dashboard():
            return self._oneshot.blocked_reason()
        if shutil.which("curl") is None:
            return _MISSING_CURL
        return None

    def ensure(self) -> None:
        reason = self.blocked_reason()
        if reason is not None:
            raise OperatorError(reason)
