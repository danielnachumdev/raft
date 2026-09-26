"""CutoverSession steps (docker/nginx/http mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.services import CutoverSession

from ..base import make_app, make_local_stack, make_stack, write_applied_app
from .base import ServicesTestCase


class TestCutoverSession(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _cutover_setup(self, _services_setup) -> None:
        self.session = self.cutover_session()

    def _docker_session(self, *, ref_text: str | None = None) -> CutoverSession:
        write_applied_app(
            self.tmp_path,
            "hub",
            source="docker",
            image="ghcr.io/org/hub",
            public_host="hub.test",
            build_context=None,
        )
        app = make_app("hub", source="docker", image="ghcr.io/org/hub", ref="main")
        stack = make_stack(
            self.tmp_path,
            (app,),
            drain_seconds=0.0,
            ready_timeout_seconds=1.0,
        )
        if ref_text is not None:
            (self.tmp_path / "deploy").mkdir(parents=True, exist_ok=True)
            (self.tmp_path / "deploy" / "hub.ref").write_text(ref_text, encoding="utf-8")
        docker = MagicMock()
        docker.router_can_fetch.return_value = True
        return CutoverSession(
            stack=stack,
            app=app,
            docker=docker,
            nginx=MagicMock(),
            http=MagicMock(),
        )

    def test_full_cutover_happy_path(self) -> None:
        s = self.session
        s.docker.service_container_id.return_value = "cid"
        s.docker.container_image_ref.return_value = "img:old"
        s.docker.container_image_id.side_effect = ["sha_old", "sha_new"]
        s.docker.router_network.return_value = "net1"
        s.docker.router_can_fetch.return_value = True
        s.http.public_host_ok.return_value = True

        with patch("raft.services.cutover.time.sleep"):
            s.snapshot_previous_image()
            assert s.previous_image == "img:old"
            assert (self.tmp_path / "deploy" / "app.image").is_file()

            s.start_tmp_from_previous()
            s.docker.run_tmp.assert_called_once_with(
                name=s.app.tmp_container,
                alias=s.app.tmp_alias,
                image="img:old",
                network="net1",
                env_file=None,
            )
            assert s.tmp_active is True

            s.shift_traffic_to_tmp()
            s.nginx.point_at.assert_called_with(s.app, "app_tmp")

            s.rebuild_stable_service()
            s.docker.rebuild_service.assert_called_with("app")

            s.shift_traffic_to_stable()
            s.nginx.point_at.assert_called_with(s.app, "app")

            s.remove_tmp()
            assert s.tmp_active is False
            assert "sha_new" in (self.tmp_path / "deploy" / "app.image").read_text(encoding="utf-8")

    def test_start_tmp_passes_env_file_and_readiness_path(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            extra={
                "envFile": "/home/raft/.raft/app.env",
                "readiness": {"type": "http", "port": "http", "path": "/ping"},
            },
        )
        s = self.session
        s.previous_image = "img:old"
        s.network = "net1"
        s.docker.router_can_fetch.return_value = True

        with patch("raft.services.cutover.time.sleep"):
            s.start_tmp_from_previous()

        s.docker.run_tmp.assert_called_once_with(
            name=s.app.tmp_container,
            alias=s.app.tmp_alias,
            image="img:old",
            network="net1",
            env_file="/home/raft/.raft/app.env",
        )
        s.docker.router_can_fetch.assert_called_with(
            s.app.tmp_alias, port=80, path="/ping"
        )

    def test_rebuild_stable_docker_pulls(self) -> None:
        session = self._docker_session(ref_text="digest\n# requested: abc123\n")
        session.rebuild_stable_service()
        session.docker.recreate_pulled_service.assert_called_once_with(
            session.app, pull_ref="ghcr.io/org/hub:abc123"
        )
        session.docker.rebuild_service.assert_not_called()

    def test_rebuild_stable_docker_defaults_ref(self) -> None:
        session = self._docker_session()
        session.rebuild_stable_service()
        session.docker.recreate_pulled_service.assert_called_once_with(
            session.app, pull_ref="ghcr.io/org/hub:main"
        )

    def test_rebuild_stable_docker_empty_requested_keeps_ref(self) -> None:
        session = self._docker_session(ref_text="digest\n# requested:   \n")
        session.rebuild_stable_service()
        session.docker.recreate_pulled_service.assert_called_once_with(
            session.app, pull_ref="ghcr.io/org/hub:main"
        )

    def test_rebuild_stable_docker_state_without_requested(self) -> None:
        session = self._docker_session(ref_text="sha256:only\n# pin: ghcr.io/org/hub:main\n")
        session.rebuild_stable_service()
        session.docker.recreate_pulled_service.assert_called_once_with(
            session.app, pull_ref="ghcr.io/org/hub:main"
        )

    def test_start_tmp_timeout_includes_container_logs(self) -> None:
        s = self.session
        s.previous_image = "img:old"
        s.network = "net1"
        s.docker.router_can_fetch.return_value = False
        s.docker.diagnostics_for.return_value = (
            '--- raft-app_tmp (container) ---\n'
            'Error: OAUTH_CLIENT_ID is required'
        )
        with patch("raft.services.cutover.time.sleep"):
            with pytest.raises(RuntimeError, match="OAUTH_CLIENT_ID") as caught:
                s.start_tmp_from_previous()
        assert "timed out waiting for: app_tmp reachable" in str(caught.value)
        s.docker.diagnostics_for.assert_called()
        kwargs = s.docker.diagnostics_for.call_args.kwargs
        assert s.app.tmp_container in kwargs.get("containers", ())

    def test_rebuild_stable_timeout_uses_app_diagnostics(self) -> None:
        s = self.session
        s.docker.rebuild_service.return_value = None
        s.docker.router_can_fetch.return_value = False
        s.docker.diagnostics_for.return_value = (
            '--- app (running/unhealthy) ---\n'
            'nginx: [emerg] host not found in upstream "old:8000"'
        )
        with patch("raft.services.cutover.time.sleep"):
            with pytest.raises(RuntimeError, match="host not found"):
                s.rebuild_stable_service()
        s.docker.diagnostics_for.assert_called_with(s.app.compose_id)

    def test_wait_ready_invokes_compose_ready_for_expose_none(self) -> None:
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
        app = make_app("app", source="docker", image="redis", public_host="")
        stack = make_stack(self.tmp_path, (app,), drain_seconds=0.0)
        docker = MagicMock()
        docker.service_is_ready.return_value = True
        session = CutoverSession(
            stack=stack,
            app=app,
            docker=docker,
            nginx=MagicMock(),
            http=MagicMock(),
        )
        with patch("raft.services.cutover.time.sleep"):
            session._wait_ready("compose ready")
        docker.service_is_ready.assert_called_with(app.compose_id)

    def test_wait_ready_uses_app_readiness_timeout(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            extra={
                "readiness": {
                    "type": "http",
                    "port": "http",
                    "timeoutSeconds": 90,
                },
            },
        )
        stack = make_local_stack(
            self.tmp_path,
            drain_seconds=0.0,
            ready_timeout_seconds=1.0,
        )
        s = CutoverSession(
            stack=stack,
            app=stack.apps[0],
            docker=MagicMock(),
            nginx=MagicMock(),
            http=MagicMock(),
        )
        s.http.public_host_ok.return_value = False
        with patch("raft.services.cutover.wait_until") as wait:
            s._wait_ready("slow ready")
        assert wait.call_args.kwargs["timeout"] == 90.0
        assert "timeoutSeconds=90s" in wait.call_args.kwargs["fix"]

    def test_wait_until_reports_budget_and_diagnostics(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from raft.errors import OperatorError
        from raft.services.wait import wait_until

        clock = {"t": 0.0}

        def mono() -> float:
            return clock["t"]

        def sleep(_seconds: float) -> None:
            clock["t"] += 0.02

        with caplog.at_level("ERROR"), patch(
            "raft.services.cutover.time.sleep", side_effect=sleep
        ), patch(
            "raft.services.cutover.time.monotonic", side_effect=mono
        ):
            with pytest.raises(OperatorError) as exc:
                wait_until(
                    "demo ready",
                    lambda: False,
                    timeout=0.01,
                    interval=0.01,
                    progress_every=0,
                    fix="raise readiness.timeoutSeconds",
                    diagnostics=lambda: "--- svc (running/starting) ---",
                )
        message = str(exc.value)
        assert "timed out waiting for: demo ready" in message
        assert "budget" in message
        assert "running/starting" in message
        assert "raise readiness.timeoutSeconds" in message
        assert "timed out waiting for: demo ready" in caplog.text

    def test_wait_until_logs_progress(self, caplog: pytest.LogCaptureFixture) -> None:
        from raft.errors import OperatorError
        from raft.services.wait import wait_until

        clock = {"t": 0.0}

        def mono() -> float:
            return clock["t"]

        def sleep(_seconds: float) -> None:
            clock["t"] += 0.1

        with caplog.at_level("INFO"), patch(
            "raft.services.cutover.time.sleep", side_effect=sleep
        ), patch(
            "raft.services.cutover.time.monotonic", side_effect=mono
        ):
            with pytest.raises(OperatorError, match="timed out waiting"):
                wait_until(
                    "slow ready",
                    lambda: False,
                    timeout=0.25,
                    interval=0.05,
                    progress_every=0.1,
                )
        assert "still waiting for: slow ready" in caplog.text

    def test_abort_cleanup_restores_stable_and_removes_tmp(self) -> None:
        s = self.session
        s.tmp_active = True
        s.abort_cleanup()
        s.nginx.point_at.assert_called_once_with(s.app, s.app.compose_id)
        s.docker.nginx_test_and_reload.assert_called_once()
        s.docker.remove_container.assert_called_once_with(s.app.tmp_container)
        assert s.tmp_active is False

    def test_abort_cleanup_swallows_restore_and_remove_errors(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        s = self.session
        s.tmp_active = True
        s.nginx.point_at.side_effect = RuntimeError("nginx down")
        s.docker.remove_container.side_effect = RuntimeError("rm failed")
        with caplog.at_level("WARNING"):
            s.abort_cleanup()
        assert "could not point nginx" in caplog.text
        assert "could not remove" in caplog.text
        assert s.tmp_active is True

    def test_abort_cleanup_noop_when_tmp_inactive(self) -> None:
        s = self.session
        s.tmp_active = False
        s.abort_cleanup()
        s.nginx.point_at.assert_not_called()
        s.docker.remove_container.assert_not_called()

    def test_wait_ready_skips_when_readiness_none(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            extra={"readiness": {"type": "none"}},
        )
        s = self.session
        with patch("raft.services.cutover.wait_until") as wait:
            s._wait_ready("noop")
        wait.assert_not_called()

    def test_log_prints(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("INFO"):
            self.session.log("hello")
        assert "hello" in caplog.text
