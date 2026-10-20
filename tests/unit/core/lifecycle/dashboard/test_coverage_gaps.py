"""Remaining dashboard coverage gaps."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.config.settings.strategies.dashboard import DashboardSettingsParser
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.dashboard.edge_render import DashboardEdgeRender
from raft.core.lifecycle.dashboard.service import DashboardService
from raft.core.lifecycle.dashboard.settings_write import DashboardSettingsWriter
from raft.services.cli.commands.dashboard import DashboardCLI
from tests.unit.base import RaftTestCase, StackMakers


class TestDashboardCoverageGaps(RaftTestCase):
    def test_auth_mode_defaults_when_omitted(self) -> None:
        cfg = DashboardSettingsParser().parse({"auth": {}})
        assert cfg.auth.mode == "none"

    def test_external_acme_without_material(self) -> None:
        cfg = DashboardConfig(
            enabled=True,
            public_host="ops.example.com",
            tls="acme",
            auth=DashboardAuthConfig(
                mode="external",
                verify_url="http://auth.demo.example/verify",
                sign_in_url="https://auth.demo.example/sign-in",
            ),
        )
        frag = DashboardEdgeRender().contribute(
            cfg,
            edge=EdgeConfig(http=80, https=443),
            data_home=Path(self.tmp_path),
        )
        assert frag.gate_tls == {}

    def test_service_enable_all_kwargs(self) -> None:
        svc = self._password_svc(running=["raft-gate", "raft-router"])
        snap = svc.enable(
            public_host="ops.example.com",
            tls="acme",
            auth_mode="password",
            verify_url="http://auth.demo.example/v",
            sign_in_url="https://auth.demo.example/s",
        )
        assert snap["enabled"] is True
        svc._docker.reload_router_nginx.assert_called_once()
        svc._docker.reload_gate_nginx.assert_called_once()

    def test_service_enable_skips_router_reload_when_router_down(self) -> None:
        svc = self._password_svc(running=[])
        svc.enable(public_host="ops.example.com", tls="acme", auth_mode="password")
        svc._docker.reload_router_nginx.assert_not_called()
        svc._docker.reload_gate_nginx.assert_not_called()

    def _password_svc(self, *, running: list[str]) -> DashboardService:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        writer = DashboardSettingsWriter(home)
        writer.set_password("correct-horse")
        svc = DashboardService(
            StackMakers.make_stack(home),
            orchestrator=MagicMock(),
            docker=MagicMock(),
            writer=writer,
        )
        svc._docker.running_services.return_value = running
        return svc

    def test_writer_clear_host_and_http_url(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        writer = DashboardSettingsWriter(home)
        writer.set_password("correct-horse")
        writer.enable(
            public_host="ops.example.com", tls="off", auth_mode="password"
        )
        assert writer.status_public()["publicUrl"].startswith("http://")
        writer.enable(public_host="")
        assert writer.load().public_host is None

    def test_writer_missing_settings_file(self) -> None:
        home = Path(self.tmp_path) / "empty-home"
        home.mkdir()
        assert DashboardSettingsWriter(home)._load_root() == {}

    def test_writer_invalid_yaml(self) -> None:
        home = Path(self.tmp_path)
        path = home / "host" / "settings.yaml"
        path.write_text(":\n  - !!", encoding="utf-8")
        with pytest.raises(OperatorError, match="cannot update"):
            DashboardSettingsWriter(home)._load_root()

    def test_writer_non_mapping_yaml(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("- list\n", encoding="utf-8")
        with pytest.raises(OperatorError, match="YAML mapping"):
            DashboardSettingsWriter(home)._load_root()

    def test_auth_raw_empty_identity(self) -> None:
        auth = DashboardAuthConfig(mode="none", identity_header="")
        raw = DashboardSettingsWriter._auth_raw(auth)
        assert "identityHeader" not in raw

    def test_cli_prints_public_url(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        writer = DashboardSettingsWriter(home)
        writer.set_password("correct-horse")
        svc = DashboardService(
            StackMakers.make_stack(home),
            orchestrator=MagicMock(),
            docker=MagicMock(),
            writer=writer,
        )
        cli = DashboardCLI(StackMakers.make_stack(home), service=svc)
        with patch("raft.services.cli.commands.dashboard.OperatorSay.say") as say:
            cli.enable(
                public_host="ops.example.com", tls="acme", auth_mode="password"
            )
        assert any("ops.example.com" in str(c) for c in say.call_args_list)
