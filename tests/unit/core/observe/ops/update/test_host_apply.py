"""HostApplyGate: dashboard uses HostOneshotGate; host needs curl."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.ops.update import HostApplyGate
from raft.core.observe.ops.update import host_apply as host_mod


class TestHostApplyGate:
    def test_allows_when_host_has_curl(self, monkeypatch) -> None:
        oneshot = MagicMock()
        oneshot.in_dashboard.return_value = False
        monkeypatch.setattr(host_mod.shutil, "which", lambda name: "/usr/bin/curl")
        gate = HostApplyGate(oneshot_gate=oneshot)
        assert gate.can_apply() is True
        assert gate.uses_host_docker() is False
        assert gate.blocked_reason() is None
        gate.ensure()

    def test_allows_dashboard_when_oneshot_ok(self) -> None:
        oneshot = MagicMock()
        oneshot.in_dashboard.return_value = True
        oneshot.can_run.return_value = True
        oneshot.blocked_reason.return_value = None
        gate = HostApplyGate(oneshot_gate=oneshot)
        assert gate.can_apply() is True
        assert gate.uses_host_docker() is True

    def test_blocks_dashboard_when_oneshot_blocked(self) -> None:
        oneshot = MagicMock()
        oneshot.in_dashboard.return_value = True
        oneshot.can_run.return_value = False
        oneshot.blocked_reason.return_value = "RAFT_HOST_HOME missing"
        gate = HostApplyGate(oneshot_gate=oneshot)
        assert gate.can_apply() is False
        assert gate.uses_host_docker() is False
        assert "RAFT_HOST_HOME" in (gate.blocked_reason() or "")
        with pytest.raises(OperatorError, match="RAFT_HOST_HOME"):
            gate.ensure()

    def test_blocks_missing_curl_on_host(self, monkeypatch) -> None:
        oneshot = MagicMock()
        oneshot.in_dashboard.return_value = False
        monkeypatch.setattr(host_mod.shutil, "which", lambda name: None)
        gate = HostApplyGate(oneshot_gate=oneshot)
        assert gate.can_apply() is False
        reason = gate.blocked_reason() or ""
        assert "curl" in reason
        with pytest.raises(OperatorError):
            gate.ensure()
