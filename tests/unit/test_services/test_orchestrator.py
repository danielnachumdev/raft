"""Orchestrator start/stop/sync/redeploy behavior (deps mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from raft.models.stack import load_stack
from raft.services import Orchestrator

from ..base import write_applied_app
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
        self.orch.docker.running_services.return_value = []
        with patch("raft.services.orchestrator.StackRenderer") as renderer_cls:
            instance = renderer_cls.return_value
            self.orch.render()
            renderer_cls.assert_called_once_with(self.orch.stack)
            instance.render.assert_called_once()
            self.orch.docker.reload_gate_nginx.assert_not_called()

    def test_render_reloads_gate_when_stamp_differs_from_disk(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        with patch(
            "raft.services.orchestrator.fingerprint_gate_nginx",
            return_value="disk-fp",
        ):
            with patch(
                "raft.services.orchestrator.read_gate_nginx_reload_stamp",
                return_value="stale-fp",
            ):
                with patch(
                    "raft.services.orchestrator.write_gate_nginx_reload_stamp"
                ) as write_stamp:
                    with patch("raft.services.orchestrator.StackRenderer"):
                        with patch("raft.services.orchestrator.require_origin_certs"):
                            self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_called_once()
        write_stamp.assert_called_once_with(self.orch.stack.root, "disk-fp")

    def test_render_reloads_gate_when_stamp_missing(self) -> None:
        """Disk already has config but gate never recorded a reload (stale process)."""
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        with patch(
            "raft.services.orchestrator.fingerprint_gate_nginx",
            return_value="on-disk",
        ):
            with patch(
                "raft.services.orchestrator.read_gate_nginx_reload_stamp",
                return_value=None,
            ):
                with patch("raft.services.orchestrator.write_gate_nginx_reload_stamp"):
                    with patch("raft.services.orchestrator.StackRenderer"):
                        with patch("raft.services.orchestrator.require_origin_certs"):
                            self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_called_once()

    def test_render_blocks_gate_reload_when_origin_certs_missing(self) -> None:
        write_applied_app(self.tmp_path, "app", public_host="app.test", tls="origin")
        orch = self.orchestrator()
        orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        with patch(
            "raft.services.orchestrator.fingerprint_gate_nginx",
            return_value="disk-fp",
        ):
            with patch(
                "raft.services.orchestrator.read_gate_nginx_reload_stamp",
                return_value="stale",
            ):
                with patch("raft.services.orchestrator.StackRenderer"):
                    with pytest.raises(RuntimeError, match="Origin certs missing"):
                        orch.render()
        orch.docker.reload_gate_nginx.assert_not_called()

    def test_render_skips_gate_reload_when_stamp_matches_disk(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        with patch(
            "raft.services.orchestrator.fingerprint_gate_nginx",
            return_value="same",
        ):
            with patch(
                "raft.services.orchestrator.read_gate_nginx_reload_stamp",
                return_value="same",
            ):
                with patch("raft.services.orchestrator.StackRenderer"):
                    self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_not_called()

    def test_render_skips_gate_reload_when_gate_down(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-router"]
        with patch(
            "raft.services.orchestrator.fingerprint_gate_nginx",
            return_value="disk-fp",
        ):
            with patch(
                "raft.services.orchestrator.read_gate_nginx_reload_stamp",
                return_value="stale",
            ):
                with patch("raft.services.orchestrator.StackRenderer"):
                    self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_not_called()

    def test_start_happy_path(self) -> None:
        self.orch.docker.running_services.side_effect = [
            [],
            ["raft-gate", "raft-router", "raft-controller", "app"],
        ]
        self.orch.http.public_host_ok.return_value = True
        with patch.object(self.orch, "sync") as sync:
            self.orch.start()
        sync.assert_called_once()
        self.orch.docker.start_stack.assert_called_once()

    def test_start_fails_if_gate_exits(self) -> None:
        self.orch.docker.running_services.side_effect = [
            [],
            ["raft-router", "app"],
        ]
        with patch.object(self.orch, "sync"):
            with pytest.raises(
                RuntimeError,
                match="missing running services: \\['raft-gate', 'raft-controller'\\]",
            ):
                self.orch.start()
        self.orch.docker.start_stack.assert_called_once()

    def test_recreate_gate_happy(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
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
        self.orch.docker.running_services.return_value = ["raft-gate"]
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
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        self.orch.http.public_host_ok.return_value = True
        self.orch.redeploy_router()
        self.orch.docker.recreate_router.assert_called_once()

    def test_wait_app_ready_uses_compose_for_expose_none_tcp(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            public_host="",
            source="docker",
            image="redis",
            build_context=None,
            extra={
                "ports": [
                    {"name": "http", "containerPort": 8000, "expose": "none"},
                ],
                "readiness": {"type": "tcp", "port": "http"},
            },
        )
        orch = self.orchestrator()
        orch.docker.service_is_ready.return_value = True
        app = orch.stack.app("app")

        with patch("raft.services.orchestrator.wait_until") as wait:
            orch._wait_app_ready(app, timeout=5)

        wait.assert_called_once()
        label = wait.call_args.args[0]
        assert label == "compose readiness for app"
        predicate = wait.call_args.args[1]
        assert predicate() is True
        orch.docker.service_is_ready.assert_called_with(app.compose_id)
        # Py3.8 branch coverage: the diagnostics lambda must run at least once.
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
        with patch("raft.services.orchestrator.wait_until") as wait:
            orch._wait_app_ready(app, timeout=5)
        wait.assert_not_called()

    def test_wait_app_ready_label_for_published_tcp(self) -> None:
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
        orch = self.orchestrator()
        orch.http.tcp_port_ok.return_value = True
        app = orch.stack.app("app")

        with patch("raft.services.orchestrator.wait_until") as wait:
            orch._wait_app_ready(app, timeout=5)

        label = wait.call_args.args[0]
        assert label == "tcp readiness for app"

    def test_redeploy_app_runs_cutover(self) -> None:
        with patch("raft.services.orchestrator.CutoverSession") as Session:
            session = MagicMock()
            Session.return_value = session
            with patch("raft.services.orchestrator.DEPLOY_CUTOVER", new=()):
                with patch.object(self.orch, "sync"):
                    self.orch.redeploy_app("app", ref_override="sha", force_sync=True)
            Session.assert_called_once()

    def test_redeploy_app_prints_error_and_reraises(self) -> None:
        step = MagicMock()
        step.key = "boom"
        step.run.side_effect = RuntimeError("cutover failed")
        with patch("raft.services.orchestrator.DEPLOY_CUTOVER", new=(step,)):
            with patch.object(self.orch, "sync"):
                with patch("raft.services.orchestrator.CutoverSession") as Session:
                    session = MagicMock()
                    Session.return_value = session
                    with pytest.raises(RuntimeError, match="cutover failed"):
                        self.orch.redeploy_app("app")
                    session.abort_cleanup.assert_called_once()

    def test_redeploy_app_abort_cleanup_failure_still_reraises(self) -> None:
        step = MagicMock()
        step.key = "boom"
        step.run.side_effect = RuntimeError("cutover failed")
        with patch("raft.services.orchestrator.DEPLOY_CUTOVER", new=(step,)):
            with patch.object(self.orch, "sync"):
                with patch("raft.services.orchestrator.CutoverSession") as Session:
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
