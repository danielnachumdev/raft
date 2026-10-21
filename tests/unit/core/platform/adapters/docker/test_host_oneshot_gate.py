"""HostOneshotGate: dashboard needs host home + docker sock + CLI."""

from __future__ import annotations

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.adapters.docker import HostOneshotGate
from raft.core.platform.adapters.docker import host_oneshot_gate as gate_mod


class TestHostOneshotGate:
    def test_not_in_dashboard_never_blocks(self, monkeypatch) -> None:
        monkeypatch.delenv("RAFT_DASHBOARD_APP_PORT", raising=False)
        gate = HostOneshotGate()
        assert gate.in_dashboard() is False
        assert gate.can_run() is True
        assert gate.blocked_reason() is None
        gate.ensure()

    def test_allows_when_home_and_docker(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DASHBOARD_APP_PORT", "18787")
        monkeypatch.setenv("RAFT_HOST_HOME", "/home/demo")
        monkeypatch.setattr(
            gate_mod.os.path, "exists", lambda p: p == "/var/run/docker.sock"
        )
        monkeypatch.setattr(
            gate_mod.shutil,
            "which",
            lambda name: "/usr/bin/docker" if name == "docker" else None,
        )
        gate = HostOneshotGate()
        assert gate.in_dashboard() is True
        assert gate.can_run() is True
        assert gate.blocked_reason() is None

    def test_blocks_without_host_home(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DASHBOARD_APP_PORT", "18787")
        monkeypatch.delenv("RAFT_HOST_HOME", raising=False)
        monkeypatch.setattr(gate_mod.os.path, "exists", lambda _p: True)
        monkeypatch.setattr(
            gate_mod.shutil, "which", lambda _n: "/usr/bin/docker"
        )
        gate = HostOneshotGate()
        assert gate.can_run() is False
        assert "RAFT_HOST_HOME" in (gate.blocked_reason() or "")
        with pytest.raises(OperatorError, match="RAFT_HOST_HOME"):
            gate.ensure()

    def test_blocks_without_docker_sock(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DASHBOARD_APP_PORT", "18787")
        monkeypatch.setenv("RAFT_HOST_HOME", "/home/demo")
        monkeypatch.setattr(gate_mod.os.path, "exists", lambda _p: False)
        monkeypatch.setattr(
            gate_mod.shutil, "which", lambda _n: "/usr/bin/docker"
        )
        gate = HostOneshotGate()
        assert "Docker socket" in (gate.blocked_reason() or "")

    def test_blocks_without_docker_cli(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DASHBOARD_APP_PORT", "18787")
        monkeypatch.setenv("RAFT_HOST_HOME", "/home/demo")
        monkeypatch.setattr(gate_mod.os.path, "exists", lambda _p: True)
        monkeypatch.setattr(gate_mod.shutil, "which", lambda _n: None)
        gate = HostOneshotGate()
        assert "`docker`" in (gate.blocked_reason() or "")

    def test_blocks_relative_host_home(self, monkeypatch) -> None:
        monkeypatch.setenv("RAFT_DASHBOARD_APP_PORT", "18787")
        monkeypatch.setenv("RAFT_HOST_HOME", "relative/home")
        monkeypatch.setattr(gate_mod.os.path, "exists", lambda _p: True)
        monkeypatch.setattr(
            gate_mod.shutil, "which", lambda _n: "/usr/bin/docker"
        )
        gate = HostOneshotGate()
        assert "RAFT_HOST_HOME" in (gate.blocked_reason() or "")
