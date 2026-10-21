"""Remaining dashboard coverage gaps."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.config.settings.dashboard_config import (
    DashboardAuthConfig,
    DashboardConfig,
)
from raft.core.core.config.settings.strategies.dashboard import DashboardSettingsParser
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.dashboard.edge_render import DashboardEdgeRender
from raft.core.lifecycle.dashboard.settings_write import DashboardSettingsWriter
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
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

    def test_redeploy_dashboard_reloads_edge_when_up(self) -> None:
        orch = self._orch(running=["raft-gate", "raft-router"])
        self._run_redeploy(orch)
        orch.docker.rebuild_service.assert_called_once_with("raft-dashboard")
        orch.docker.reload_router_nginx.assert_called_once()
        orch.docker.reload_gate_nginx.assert_called_once()

    def test_redeploy_dashboard_skips_reload_when_edge_down(self) -> None:
        orch = self._orch(running=[])
        self._run_redeploy(orch)
        orch.docker.reload_router_nginx.assert_not_called()
        orch.docker.reload_gate_nginx.assert_not_called()

    def _run_redeploy(self, orch: Orchestrator) -> None:
        with patch("raft.core.lifecycle.deploy.orchestrator.service.StackLock"):
            with patch(
                "raft.core.lifecycle.deploy.orchestrator.service.StackRenderer"
            ) as renderer:
                renderer.return_value.render = MagicMock()
                with patch("raft.core.lifecycle.acme.ensure.AcmeEnsure"):
                    with patch("raft.core.lifecycle.acme.install.AcmeGateInstall"):
                        with patch(
                            "raft.core.lifecycle.deploy.orchestrator.service."
                            "GraphEventStore"
                        ):
                            with patch(
                                "raft.core.lifecycle.deploy.orchestrator.service."
                                "OperatorSay.say"
                            ):
                                orch.redeploy_dashboard()

    def _orch(self, *, running: list[str]) -> Orchestrator:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text(
            "dashboard:\n  enabled: true\n", encoding="utf-8"
        )
        orch = Orchestrator(StackMakers.make_stack(home))
        orch.docker = MagicMock()
        orch.docker.running_services.return_value = running
        return orch

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

    def test_writer_status_public_url(self) -> None:
        home = Path(self.tmp_path)
        (home / "host" / "settings.yaml").write_text("{}\n", encoding="utf-8")
        writer = DashboardSettingsWriter(home)
        writer.set_password("correct-horse")
        writer.enable(
            public_host="ops.example.com", tls="acme", auth_mode="password"
        )
        assert "ops.example.com" in (writer.status_public()["publicUrl"] or "")
