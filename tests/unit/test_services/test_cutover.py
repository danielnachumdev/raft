"""CutoverSession steps (docker/nginx/http mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.services import CutoverSession

from ..base import make_app, make_stack, write_applied_app
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

            s.shift_traffic_to_tmp()
            s.nginx.point_at.assert_called_with(s.app, "app_tmp")

            s.rebuild_stable_service()
            s.docker.rebuild_service.assert_called_with("app")

            s.shift_traffic_to_stable()
            s.nginx.point_at.assert_called_with(s.app, "app")

            s.remove_tmp()
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

    def test_log_prints(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("INFO"):
            self.session.log("hello")
        assert "hello" in caplog.text
