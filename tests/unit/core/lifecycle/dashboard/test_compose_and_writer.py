"""Compose yaml + settings writer + password coverage."""

from pathlib import Path

import pytest
import yaml

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.dashboard.compose_yaml import DashboardComposeYaml
from raft.core.lifecycle.dashboard.password import DashboardPassword
from raft.core.lifecycle.dashboard.settings_write import DashboardSettingsWriter
from raft.core.lifecycle.dashboard.target import DashboardTarget
from tests.unit.base import RaftTestCase


class TestDashboardComposeAndWriter(RaftTestCase):
    def test_compose_empty_when_disabled(self) -> None:
        empty = DashboardComposeYaml().build(DashboardConfig())
        assert "services: {}" in empty

    def test_compose_enabled_injects_host_home(self) -> None:
        text = DashboardComposeYaml().build(
            DashboardConfig(enabled=True, port=8787)
        )
        self._assert_compose_runtime(text)
        self._assert_compose_volumes(text)
        self._assert_compose_resources(text)

    def _assert_compose_runtime(self, text: str) -> None:
        assert "raft-dashboard" in text
        assert "127.0.0.1:8787:8787" in text
        assert 'RAFT_DASHBOARD_APP_PORT: "18787"' in text
        assert 'RAFT_HOST_HOME: "${RAFT_HOST_HOME}"' in text
        assert 'RAFT_HOST_UID: "${RAFT_HOST_UID:-0}"' in text
        assert 'RAFT_HOST_GID: "${RAFT_HOST_GID:-0}"' in text
        assert 'HOME: "${RAFT_HOST_HOME}"' in text
        assert 'RAFT_SSH_DIR: "${RAFT_HOST_HOME}/.ssh"' in text
        assert 'user: "${RAFT_HOST_UID:-0}:${RAFT_HOST_GID:-0}"' in text
        assert "RAFT_HOST_DOCKER_BIN" in text
        assert "RAFT_HOST_DOCKER_PLUGIN_DIR" in text
        assert "RAFT_SERVE_BIND" not in text
        assert "oauth.env" not in text

    def _assert_compose_volumes(self, text: str) -> None:
        assert '"${RAFT_HOST_HOME}/.local:${RAFT_HOST_HOME}/.local:ro"' in text
        assert '"${RAFT_HOST_HOME}/.ssh:${RAFT_HOST_HOME}/.ssh"' in text
        assert "/etc/hostname:/etc/host_hostname:ro" in text
        assert ".:/raft:ro" in text
        assert "./compose.yaml:/raft/compose.yaml" in text
        assert "./host/gate-nginx.fingerprint:/raft/host/gate-nginx.fingerprint" in text
        assert (
            "./host/router-nginx.fingerprint:/raft/host/router-nginx.fingerprint"
            in text
        )
        assert "./host/inbox:/raft/host/inbox" in text

    def _assert_compose_resources(self, text: str) -> None:
        assert 'cpus: "1.0"' in text
        assert "memory: 256M" in text

    def test_compose_oauth_env_file(self) -> None:
        oauth = DashboardComposeYaml().build(
            DashboardConfig(
                enabled=True,
                port=8787,
                auth=DashboardAuthConfig(mode="oauth"),
            )
        )
        assert "./host/secrets/dashboard/oauth.env" in oauth

    def test_password_roundtrip_and_bad(self) -> None:
        pw = DashboardPassword()
        hashed = pw.hash("correct-horse")
        assert pw.verify("correct-horse", hashed)
        assert not pw.verify("wrong", hashed)
        assert not pw.verify("x", None)
        assert not pw.verify("x", "not-a-hash")
        assert not pw.verify("x", "pbkdf2_sha256$bad$salt$dig")

    def test_writer_enable_disable_password(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("edge: {http: 80}\n", encoding="utf-8")
        writer = DashboardSettingsWriter(home)
        writer.set_password("correct-horse")
        writer.enable(
            public_host="ops.example.com",
            tls="acme",
            auth_mode="password",
        )
        snap = writer.status_public()
        assert snap["enabled"] is True
        assert snap["publicUrl"] == "https://ops.example.com/"
        assert snap["auth"]["hasPasswordHash"] is True
        writer.disable()
        assert writer.load().enabled is False

    def test_writer_short_password(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="at least 8"):
            DashboardSettingsWriter(home).set_password("short")

    def test_writer_enable_public_needs_password(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="requires a password"):
            DashboardSettingsWriter(home).enable(
                public_host="ops.example.com",
                tls="acme",
                auth_mode="password",
            )

    def test_target_firewall_apps(self) -> None:
        cfg = DashboardConfig(
            enabled=True,
            public_host="ops.example.com",
            tls="acme",
            auth=DashboardAuthConfig(mode="password", password_hash="x"),
        )
        apps = DashboardTarget().firewall_apps(cfg)
        assert len(apps) == 1
        assert apps[0].name == "raft-dashboard"
        assert DashboardTarget().firewall_apps(DashboardConfig()) == []

    def test_writer_corrupt_settings(self) -> None:
        home = Path(self.tmp_path)
        path = home / "host" / "settings.yaml"
        path.write_text("- not a mapping\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="YAML mapping"):
            DashboardSettingsWriter(home).enable()
