"""Orchestrator selects DeploymentMethod from AppSpec; up vs down dispatch."""

from __future__ import annotations

from unittest.mock import patch

from raft.models.state.scaling_store import ScalingStore

from tests.unit.base import write_applied_app
from ..orchestrator.base import OrchestratorTestCase


class TestDeploymentMethodSelection(OrchestratorTestCase):
    def test_default_method_is_seamless(self) -> None:
        assert self.orch._method_id(self.orch.stack.app("app")) == "seamless"

    def test_inplace_from_manifest(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            public_host="app.test",
            extra={"deployment": {"method": "inplace"}},
        )
        orch = self.orchestrator()
        assert orch._method_id(orch.stack.app("app")) == "inplace"

    def test_seamless_dual_runs_when_up(self) -> None:
        self.set_edge_running("app")
        with patch("raft.deploy.methods.strategies.seamless.CutoverSession") as Session:
            with patch("raft.deploy.methods.strategies.seamless.DEPLOY_CUTOVER", new=()):
                with patch.object(self.orch, "sync"):
                    self.orch.redeploy_app("app")
        Session.assert_called_once()
        self.orch.docker.stop_service.assert_not_called()
        self.orch.docker.run_tmp.assert_not_called()

    def test_inplace_does_not_start_tmp_when_up(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            public_host="app.test",
            extra={"deployment": {"method": "inplace"}},
        )
        orch = self.orchestrator()
        self.set_edge_running("app", orch=orch)
        self.stub_http_ready(orch.http)
        with patch.object(orch, "sync"):
            orch.redeploy_app("app")
        orch.docker.stop_service.assert_called_once_with("app")
        orch.docker.rebuild_service.assert_called_once_with("app")
        orch.docker.run_tmp.assert_not_called()
        orch.docker.remove_container.assert_called_once()

    def test_inplace_down_path_single_generation(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            public_host="app.test",
            extra={"deployment": {"method": "inplace"}},
        )
        orch = self.orchestrator()
        self.set_edge_only(orch=orch)
        self.stub_http_ready(orch.http)
        with patch("raft.deploy.methods.strategies.seamless.CutoverSession") as Session:
            with patch.object(orch, "sync"):
                orch.redeploy_app("app")
        Session.assert_not_called()
        orch.docker.stop_service.assert_not_called()
        orch.docker.rebuild_service.assert_called_once_with("app")

    def test_seamless_down_when_scaled_idle(self) -> None:
        self.set_edge_running("app")
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        self.stub_http_ready(self.orch.http)
        with patch("raft.deploy.methods.strategies.seamless.CutoverSession") as Session:
            with patch.object(self.orch, "sync"):
                self.orch.redeploy_app("app")
        Session.assert_not_called()
        self.orch.docker.rebuild_service.assert_called_once_with("app")

    def test_method_id_defaults_on_spec_error(self) -> None:
        from raft.errors.cta import OperatorError
        from raft.models.stack import Stack

        app = self.orch.stack.app("app")
        with patch.object(Stack, "spec_for", side_effect=OperatorError("boom")):
            assert self.orch._method_id(app) == "seamless"
