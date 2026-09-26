"""Orchestrator wait/redeploy/ensure."""

from unittest.mock import MagicMock, patch

import pytest

from raft.models.stack import load_stack
from raft.services.deploy.orchestrator import Orchestrator

from ....base import write_applied_app
from .base import OrchestratorTestCase


class TestOrchRedeploy(OrchestratorTestCase):
    def test_wait_app_ready_uses_compose_for_expose_none_tcp(self) -> None:
        self._seed_expose_none_tcp()
        orch = self.orchestrator()
        orch.docker.service_is_ready.return_value = True
        app = orch.stack.app("app")
        with patch("raft.services.deploy.orchestrator.wait_until") as wait:
            orch._wait_app_ready(app, timeout=5)
        self._assert_compose_ready_wait(orch, app, wait)

    def _seed_expose_none_tcp(self) -> None:
        write_applied_app(
            self.tmp_path, "app", public_host="", source="docker", image="redis",
            build_context=None,
            extra={
                "ports": [{"name": "http", "containerPort": 8000, "expose": "none"}],
                "readiness": {"type": "tcp", "port": "http"},
            },
        )

    def _assert_compose_ready_wait(self, orch, app, wait) -> None:
        wait.assert_called_once()
        assert wait.call_args.args[0] == "compose readiness for app"
        assert wait.call_args.args[1]() is True
        orch.docker.service_is_ready.assert_called_with(app.compose_id)
        diag = wait.call_args.kwargs["diagnostics"]
        orch.docker.diagnostics_for.return_value = "--- app ---"
        assert diag() == "--- app ---"
        orch.docker.diagnostics_for.assert_called_with(app.compose_id)

    def test_wait_app_ready_skips_when_readiness_none(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            extra={"readiness": {"type": "none"}},
        )
        orch = self.orchestrator()
        app = orch.stack.app("app")
        with patch("raft.services.deploy.orchestrator.wait_until") as wait:
            orch._wait_app_ready(app, timeout=5)
        wait.assert_not_called()

    def test_wait_app_ready_label_for_published_tcp(self) -> None:
        self._test_wait_app_ready_label_for_published_tcp_p1()
        self._test_wait_app_ready_label_for_published_tcp_p2()

    def _test_wait_app_ready_label_for_published_tcp_p1(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            public_host="",
            source="docker",
            image="redis",
            build_context=None,
            extra={
                "ports": [
                    {
                        "name": "smtp",
                        "containerPort": 25,
                        "expose": "host",
                        "publicPort": 25,
                    },
                ],
                "readiness": {"type": "tcp", "port": "smtp"},
            },
        )

    def _test_wait_app_ready_label_for_published_tcp_p2(self) -> None:
        orch = self.orchestrator()
        orch.http.tcp_port_ok.return_value = True
        app = orch.stack.app("app")

        with patch("raft.services.deploy.orchestrator.wait_until") as wait:
            orch._wait_app_ready(app, timeout=5)

        label = wait.call_args.args[0]
        assert label == "tcp readiness for app"

    def test_redeploy_app_runs_cutover(self) -> None:
        with patch("raft.services.deploy.orchestrator_deploy.CutoverSession") as Session:
            session = MagicMock()
            Session.return_value = session
            with patch("raft.services.deploy.orchestrator_deploy.DEPLOY_CUTOVER", new=()):
                with patch.object(self.orch, "sync"):
                    self.orch.redeploy_app("app", ref_override="sha", force_sync=True)
            Session.assert_called_once()

    def test_redeploy_app_prints_error_and_reraises(self) -> None:
        step = MagicMock()
        step.key = "boom"
        step.run.side_effect = RuntimeError("cutover failed")
        with patch("raft.services.deploy.orchestrator_deploy.DEPLOY_CUTOVER", new=(step,)):
            with patch.object(self.orch, "sync"):
                with patch("raft.services.deploy.orchestrator_deploy.CutoverSession") as Session:
                    session = MagicMock()
                    Session.return_value = session
                    with pytest.raises(RuntimeError, match="cutover failed"):
                        self.orch.redeploy_app("app")
                    session.abort_cleanup.assert_called_once()

    def test_redeploy_app_abort_cleanup_failure_still_reraises(self) -> None:
        step = MagicMock()
        step.key = "boom"
        step.run.side_effect = RuntimeError("cutover failed")
        with patch("raft.services.deploy.orchestrator_deploy.DEPLOY_CUTOVER", new=(step,)):
            with patch.object(self.orch, "sync"):
                with patch("raft.services.deploy.orchestrator_deploy.CutoverSession") as Session:
                    session = MagicMock()
                    session.abort_cleanup.side_effect = RuntimeError("cleanup boom")
                    Session.return_value = session
                    with pytest.raises(RuntimeError, match="cutover failed"):
                        self.orch.redeploy_app("app")
                    session.abort_cleanup.assert_called_once()

    def test_ensure_app_deployed_redeploys_when_running(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller", "app"]
        with patch.object(self.orch, "redeploy_app") as redeploy:
            self.orch.ensure_app_deployed("app", ref_override="sha", force_sync=True)
        redeploy.assert_called_once_with("app", ref_override="sha", force_sync=True)

    def test_ensure_app_deployed_starts_app_when_edge_up(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        self.orch.http.public_host_ok.return_value = True
        with patch.object(self.orch, "sync") as sync:
            self.orch.ensure_app_deployed("app", ref_override="v1", force_sync=True)
        sync.assert_called_once_with(["app"], ref_override="v1", force=True)
        self.orch.docker.rebuild_service.assert_called_once_with("app")
        self.orch.docker.nginx_test_and_reload.assert_called_once()

    def test_ensure_app_deployed_full_up_when_cold(self) -> None:
        self.orch.docker.running_services.side_effect = [
            [],
            [],
            ["raft-gate", "raft-router", "raft-controller", "app"],
        ]
        self.orch.http.public_host_ok.return_value = True
        with patch.object(self.orch, "sync") as sync:
            self.orch.ensure_app_deployed("app", ref_override="main", force_sync=False)
        sync.assert_called_once_with(["app"], ref_override="main", force=False)
        self.orch.docker.start_stack.assert_called_once()

    def test_ensure_app_deployed_cold_syncs_other_apps(self) -> None:
        write_applied_app(self.tmp_path, "other", public_host="other.test")
        stack = load_stack(self.tmp_path)
        orch = Orchestrator(stack)
        orch.docker = MagicMock()
        orch.nginx = MagicMock()
        orch.http = MagicMock()
        orch.syncer = MagicMock()
        orch.docker.running_services.side_effect = [
            [],
            [],
            ["raft-gate", "raft-router", "raft-controller", "app", "other"],
        ]
        orch.http.public_host_ok.return_value = True
        with patch.object(orch, "sync") as sync:
            orch.ensure_app_deployed("app", force_sync=True)
        assert sync.call_args_list[0].args[0] == ["app"]
        assert sync.call_args_list[1].args[0] == ["other"]

    def test_ensure_app_deployed_cold_refuses_partial_stack(self) -> None:
        self.orch.docker.running_services.side_effect = [
            ["router"],
            ["router"],
        ]
        with pytest.raises(RuntimeError, match="already running"):
            self.orch.ensure_app_deployed("app")
