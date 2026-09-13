"""Orchestrator start/stop/sync/redeploy behavior (deps mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from .base import ServicesTestCase

class TestOrchestrator(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _orch_setup(self, _services_setup) -> None:
        self.orch = self.orchestrator()

    def test_sync_ensures_upstreams_then_syncer(self) -> None:
        with patch.object(self.orch, "render"):
            self.orch.sync(["app"], ref_override="abc", force=True)
        self.orch.nginx.ensure_steady_file.assert_called()
        self.orch.syncer.sync.assert_called_once()

    def test_sync_all_apps(self) -> None:
        with patch.object(self.orch, "render"):
            self.orch.sync()
        assert self.orch.syncer.sync.call_args.args[0] == list(self.orch.stack.apps)

    def test_render_invokes_stack_renderer(self) -> None:
        with patch("raft.services.orchestrator.StackRenderer") as renderer_cls:
            instance = renderer_cls.return_value
            self.orch.render()
            renderer_cls.assert_called_once_with(self.orch.stack)
            instance.render.assert_called_once()

    def test_start_happy_path(self) -> None:
        self.orch.docker.running_services.return_value = []
        self.orch.http.public_host_ok.return_value = True
        with patch.object(self.orch, "sync") as sync:
            self.orch.start()
        sync.assert_called_once()
        self.orch.docker.start_stack.assert_called_once()

    def test_recreate_gate_happy(self) -> None:
        self.orch.docker.running_services.return_value = ["gate", "router"]
        self.orch.http.tcp_port_ok.return_value = True
        with patch.object(self.orch, "render"):
            self.orch.recreate_gate()
        self.orch.docker.recreate_gate.assert_called_once()

    def test_stop_already_stopped(self) -> None:
        self.orch.docker.running_services.return_value = []
        self.orch.stop()
        self.orch.docker.remove_container.assert_called()
        self.orch.docker.stop_stack.assert_not_called()

    def test_stop_running(self) -> None:
        self.orch.docker.running_services.return_value = ["gate"]
        self.orch.stop()
        self.orch.docker.stop_stack.assert_called_once()

    def test_redeploy_routes_to_router_and_app(self) -> None:
        with patch.object(self.orch, "redeploy_router") as rr:
            self.orch.redeploy("router")
        rr.assert_called_once()
        with patch.object(self.orch, "redeploy_app") as ra:
            self.orch.redeploy("app")
        ra.assert_called_once_with("app")

    def test_redeploy_router_happy(self) -> None:
        self.orch.docker.running_services.return_value = ["gate", "router"]
        self.orch.http.public_host_ok.return_value = True
        self.orch.redeploy_router()
        self.orch.docker.recreate_router.assert_called_once()

    def test_redeploy_app_runs_cutover(self) -> None:
        with patch("raft.services.orchestrator.CutoverSession") as Session:
            session = MagicMock()
            Session.return_value = session
            with patch("raft.services.orchestrator.DEPLOY_CUTOVER", new=()):
                with patch.object(self.orch, "sync"):
                    self.orch.redeploy_app(
                        "app", ref_override="sha", force_sync=True
                    )
            Session.assert_called_once()

    def test_redeploy_app_prints_error_and_reraises(self) -> None:
        step = MagicMock()
        step.key = "boom"
        step.run.side_effect = RuntimeError("cutover failed")
        with patch("raft.services.orchestrator.DEPLOY_CUTOVER", new=(step,)):
            with patch.object(self.orch, "sync"):
                with pytest.raises(RuntimeError, match="cutover failed"):
                    self.orch.redeploy_app("app")
