"""HostApplyGate: dashboard container and missing curl refuse SelfUpdate."""

from __future__ import annotations

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.ops.update import HostApplyGate
from raft.core.observe.ops.update import host_apply as host_mod


class TestHostApplyGate:
    def test_allows_when_host_has_curl(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_DASHBOARD_APP_PORT", raising=False)
        monkeypatch.setattr(host_mod.shutil, "which", lambda name: "/usr/bin/curl")
        gate = HostApplyGate()
        assert gate.can_apply() is True
        assert gate.blocked_reason() is None
        gate.ensure()

    def test_blocks_dashboard_container(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DASHBOARD_APP_PORT", "18787")
        monkeypatch.setattr(host_mod.shutil, "which", lambda name: "/usr/bin/curl")
        gate = HostApplyGate()
        assert gate.can_apply() is False
        reason = gate.blocked_reason() or ""
        assert "dashboard container" in reason
        assert "raft update" in reason
        with pytest.raises(OperatorError) as exc:
            gate.ensure()
        assert "dashboard container" in str(exc.value)

    def test_blocks_missing_curl(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_DASHBOARD_APP_PORT", raising=False)
        monkeypatch.setattr(host_mod.shutil, "which", lambda name: None)
        gate = HostApplyGate()
        assert gate.can_apply() is False
        reason = gate.blocked_reason() or ""
        assert "curl" in reason
        with pytest.raises(OperatorError):
            gate.ensure()
