"""Orchestrator wait/redeploy/ensure."""

from unittest.mock import MagicMock, patch

import pytest

from raft.models.stack import load_stack
from raft.deploy.orchestrator import Orchestrator
from tests.shared.compose_ids import RunningServices

from tests.unit.base import write_applied_app
from .base import OrchestratorTestCase


class TestOrchRedeploy(OrchestratorTestCase):
    def test_wait_app_ready_uses_compose_for_expose_none_tcp(self) -> None:
        self._seed_expose_none_tcp()
        orch = self.orchestrator()
        orch.docker.service_is_ready.return_value = True
        app = orch.stack.app("app")
        with patch("raft.deploy.orchestrator.wait_until") as wait:
            orch._wait_app_ready(app, timeout=5)
        self._assert_compose_ready_wait(orch, app, wait)

    def _seed_expose_none_tcp(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            public_host="",
            source="docker",
            image="redis",
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
        with patch("raft.deploy.orchestrator.wait_until") as wait:
            orch._wait_app_ready(app, timeout=5)
        wait.assert_not_called()

    def test_wait_app_ready_skips_scaled_to_zero_host(self) -> None:
        from raft.models.state.scaling_store import ScalingStore

        write_applied_app(
            self.tmp_path,
            "app",
            public_host="app.test",
            extra={"readiness": {"type": "http", "port": "http", "path": "/health"}},
        )
        orch = self.orchestrator()
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        app = orch.stack.app("app")
        with patch("raft.deploy.orchestrator.wait_until") as wait:
            orch._wait_app_ready(app, timeout=5)
        wait.assert_not_called()

    def test_skip_scaled_host_wait_requires_public_host(self) -> None:
        from raft.models.app import App

        orch = self.orchestrator()
        app = App(name="internal", public_host="", source="local", path="apps/x")
        assert orch._skip_scaled_host_wait(app) is False

    def test_wait_app_ready_label_includes_readiness_path(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            public_host="app.test",
            extra={"readiness": {"type": "http", "port": "http", "path": "/health"}},
        )
        orch = self.orchestrator()
        self.stub_http_ready(orch.http)
        app = orch.stack.app("app")
        with patch("raft.deploy.orchestrator.wait_until") as wait:
            orch._wait_app_ready(app, timeout=5)
        assert wait.call_args.args[0] == "Host app.test/health"

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

        with patch("raft.deploy.orchestrator.wait_until") as wait:
            orch._wait_app_ready(app, timeout=5)

        label = wait.call_args.args[0]
        assert label == "tcp readiness for app"

    def test_redeploy_app_runs_cutover(self) -> None:
        self.set_edge_running("app")
        with patch("raft.deploy.methods.strategies.seamless.CutoverSession") as Session:
            session = MagicMock()
            Session.return_value = session
            with patch("raft.deploy.methods.strategies.seamless.DEPLOY_CUTOVER", new=()):
                with patch.object(self.orch, "sync"):
                    self.orch.redeploy_app("app", ref_override="sha", force_sync=True)
            Session.assert_called_once()

    def test_redeploy_app_prints_error_and_reraises(self) -> None:
        self.set_edge_running("app")
        step = MagicMock()
        step.key = "boom"
        step.run.side_effect = RuntimeError("cutover failed")
        with patch("raft.deploy.methods.strategies.seamless.DEPLOY_CUTOVER", new=(step,)):
            with patch.object(self.orch, "sync"):
                with patch("raft.deploy.methods.strategies.seamless.CutoverSession") as Session:
                    session = MagicMock()
                    Session.return_value = session
                    with pytest.raises(RuntimeError, match="cutover failed"):
                        self.orch.redeploy_app("app")
                    session.abort_cleanup.assert_called_once()

    def test_redeploy_app_abort_cleanup_failure_still_reraises(self) -> None:
        self.set_edge_running("app")
        step = MagicMock()
        step.key = "boom"
        step.run.side_effect = RuntimeError("cutover failed")
        with patch("raft.deploy.methods.strategies.seamless.DEPLOY_CUTOVER", new=(step,)):
            with patch.object(self.orch, "sync"):
                with patch("raft.deploy.methods.strategies.seamless.CutoverSession") as Session:
                    session = MagicMock()
                    session.abort_cleanup.side_effect = RuntimeError("cleanup boom")
                    Session.return_value = session
                    with pytest.raises(RuntimeError, match="cutover failed"):
                        self.orch.redeploy_app("app")
                    session.abort_cleanup.assert_called_once()

    def test_ensure_app_deployed_cutover_when_running(self) -> None:
        self.set_edge_running("app")
        with patch("raft.deploy.methods.strategies.seamless.CutoverSession") as Session:
            with patch("raft.deploy.methods.strategies.seamless.DEPLOY_CUTOVER", new=()):
                with patch.object(self.orch, "sync") as sync:
                    self.orch.ensure_app_deployed(
                        "app", ref_override="sha", force_sync=True
                    )
        sync.assert_called_once_with(["app"], ref_override="sha", force=True)
        Session.assert_called_once()

    def test_ensure_app_deployed_starts_app_when_edge_up(self) -> None:
        self.set_edge_only()
        self.stub_http_ready(self.orch.http)
        with patch.object(self.orch, "sync") as sync:
            self.orch.ensure_app_deployed("app", ref_override="v1", force_sync=True)
        sync.assert_called_once_with(["app"], ref_override="v1", force=True)
        self.orch.docker.rebuild_service.assert_called_once_with("app")
        self.orch.docker.nginx_test_and_reload.assert_called_once()

    def test_ensure_app_deployed_full_up_when_cold(self) -> None:
        self.orch.docker.running_services.side_effect = [
            [],
            [],
            RunningServices.with_apps("app"),
        ]
        self.stub_http_ready(self.orch.http)
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
            RunningServices.with_apps("app", "other"),
        ]
        self.stub_http_ready(orch.http)
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

    def test_ensure_acme_best_effort_swallows_errors(self) -> None:
        with patch(
            "raft.deploy.orchestrator_deploy.AcmeEnsure",
            side_effect=RuntimeError("acme boom"),
        ):
            self.orch._ensure_acme_best_effort(["app"])
