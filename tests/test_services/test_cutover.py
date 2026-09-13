"""CutoverSession steps (docker/nginx/http mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from ..base import make_app, make_stack
from .base import ServicesTestCase
from raft.services import CutoverSession

class TestCutoverSession(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _cutover_setup(self, _services_setup) -> None:
        self.session = self.cutover_session()

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
            s.docker.run_tmp.assert_called_once()

            s.shift_traffic_to_tmp()
            s.nginx.point_at.assert_called_with(s.app, "app_tmp")

            s.rebuild_stable_service()
            s.docker.rebuild_service.assert_called_with("app")

            s.shift_traffic_to_stable()
            s.nginx.point_at.assert_called_with(s.app, "app")

            s.remove_tmp()
            assert "sha_new" in (
                self.tmp_path / "deploy" / "app.image"
            ).read_text(encoding="utf-8")

    def test_rebuild_stable_docker_pulls(self) -> None:
        app = make_app(
            "hub", source="docker", image="ghcr.io/org/hub", ref="main"
        )
        stack = make_stack(
            self.tmp_path,
            (app,),
            drain_seconds=0.0,
            ready_timeout_seconds=1.0,
        )
        (self.tmp_path / "deploy").mkdir(parents=True, exist_ok=True)
        (self.tmp_path / "deploy" / "hub.ref").write_text(
            "digest\n# requested: abc123\n", encoding="utf-8"
        )
        docker = MagicMock()
        docker.router_can_fetch.return_value = True
        session = CutoverSession(
            stack=stack,
            app=app,
            docker=docker,
            nginx=MagicMock(),
            http=MagicMock(),
        )
        session.rebuild_stable_service()
        docker.recreate_pulled_service.assert_called_once_with(
            app, pull_ref="ghcr.io/org/hub:abc123"
        )
        docker.rebuild_service.assert_not_called()

    def test_rebuild_stable_docker_defaults_ref(self) -> None:
        app = make_app(
            "hub", source="docker", image="ghcr.io/org/hub", ref="main"
        )
        stack = make_stack(
            self.tmp_path,
            (app,),
            drain_seconds=0.0,
            ready_timeout_seconds=1.0,
        )
        docker = MagicMock()
        docker.router_can_fetch.return_value = True
        session = CutoverSession(
            stack=stack,
            app=app,
            docker=docker,
            nginx=MagicMock(),
            http=MagicMock(),
        )
        session.rebuild_stable_service()
        docker.recreate_pulled_service.assert_called_once_with(
            app, pull_ref="ghcr.io/org/hub:main"
        )

    def test_rebuild_stable_docker_empty_requested_keeps_ref(self) -> None:
        app = make_app(
            "hub", source="docker", image="ghcr.io/org/hub", ref="main"
        )
        stack = make_stack(
            self.tmp_path,
            (app,),
            drain_seconds=0.0,
            ready_timeout_seconds=1.0,
        )
        (self.tmp_path / "deploy").mkdir(parents=True, exist_ok=True)
        (self.tmp_path / "deploy" / "hub.ref").write_text(
            "digest\n# requested:   \n", encoding="utf-8"
        )
        docker = MagicMock()
        docker.router_can_fetch.return_value = True
        session = CutoverSession(
            stack=stack,
            app=app,
            docker=docker,
            nginx=MagicMock(),
            http=MagicMock(),
        )
        session.rebuild_stable_service()
        docker.recreate_pulled_service.assert_called_once_with(
            app, pull_ref="ghcr.io/org/hub:main"
        )

    def test_rebuild_stable_docker_state_without_requested(self) -> None:
        app = make_app(
            "hub", source="docker", image="ghcr.io/org/hub", ref="main"
        )
        stack = make_stack(
            self.tmp_path,
            (app,),
            drain_seconds=0.0,
            ready_timeout_seconds=1.0,
        )
        (self.tmp_path / "deploy").mkdir(parents=True, exist_ok=True)
        (self.tmp_path / "deploy" / "hub.ref").write_text(
            "sha256:only\n# pin: ghcr.io/org/hub:main\n", encoding="utf-8"
        )
        docker = MagicMock()
        docker.router_can_fetch.return_value = True
        session = CutoverSession(
            stack=stack,
            app=app,
            docker=docker,
            nginx=MagicMock(),
            http=MagicMock(),
        )
        session.rebuild_stable_service()
        docker.recreate_pulled_service.assert_called_once_with(
            app, pull_ref="ghcr.io/org/hub:main"
        )

    def test_log_prints(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level("INFO"):
            self.session.log("hello")
        assert "hello" in caplog.text
