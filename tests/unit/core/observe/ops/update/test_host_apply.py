"""HostApplyGate: dashboard needs host home + docker; host needs curl."""

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
        assert gate.uses_host_docker() is False
        assert gate.blocked_reason() is None
        gate.ensure()

    def test_allows_dashboard_when_host_home_and_docker(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DASHBOARD_APP_PORT", "18787")
        monkeypatch.setenv("RAFT_HOST_HOME", "/home/demo")
        monkeypatch.setattr(host_mod.os.path, "exists", lambda p: p == "/var/run/docker.sock")
        monkeypatch.setattr(
            host_mod.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None
        )
        gate = HostApplyGate()
        assert gate.can_apply() is True
        assert gate.uses_host_docker() is True
        assert gate.blocked_reason() is None

    def test_blocks_dashboard_without_host_home(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DASHBOARD_APP_PORT", "18787")
        monkeypatch.delenv("RAFT_HOST_HOME", raising=False)
        monkeypatch.setattr(host_mod.os.path, "exists", lambda p: True)
        monkeypatch.setattr(host_mod.shutil, "which", lambda name: "/usr/bin/docker")
        gate = HostApplyGate()
        assert gate.can_apply() is False
        assert gate.uses_host_docker() is False
        reason = gate.blocked_reason() or ""
        assert "RAFT_HOST_HOME" in reason
        with pytest.raises(OperatorError) as exc:
            gate.ensure()
        assert "RAFT_HOST_HOME" in str(exc.value)

    def test_blocks_dashboard_relative_host_home(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DASHBOARD_APP_PORT", "18787")
        monkeypatch.setenv("RAFT_HOST_HOME", "relative/home")
        monkeypatch.setattr(host_mod.os.path, "exists", lambda p: True)
        monkeypatch.setattr(host_mod.shutil, "which", lambda name: "/usr/bin/docker")
        gate = HostApplyGate()
        assert gate.can_apply() is False
        assert "RAFT_HOST_HOME" in (gate.blocked_reason() or "")

    def test_blocks_dashboard_without_docker_sock(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DASHBOARD_APP_PORT", "18787")
        monkeypatch.setenv("RAFT_HOST_HOME", "/home/demo")
        monkeypatch.setattr(host_mod.os.path, "exists", lambda p: False)
        monkeypatch.setattr(host_mod.shutil, "which", lambda name: "/usr/bin/docker")
        gate = HostApplyGate()
        assert gate.can_apply() is False
        assert "Docker socket" in (gate.blocked_reason() or "")

    def test_blocks_dashboard_without_docker_cli(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DASHBOARD_APP_PORT", "18787")
        monkeypatch.setenv("RAFT_HOST_HOME", "/home/demo")
        monkeypatch.setattr(host_mod.os.path, "exists", lambda p: True)
        monkeypatch.setattr(host_mod.shutil, "which", lambda name: None)
        gate = HostApplyGate()
        assert gate.can_apply() is False
        assert "`docker`" in (gate.blocked_reason() or "")

    def test_blocks_missing_curl_on_host(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_DASHBOARD_APP_PORT", raising=False)
        monkeypatch.setattr(host_mod.shutil, "which", lambda name: None)
        gate = HostApplyGate()
        assert gate.can_apply() is False
        reason = gate.blocked_reason() or ""
        assert "curl" in reason
        with pytest.raises(OperatorError):
            gate.ensure()
