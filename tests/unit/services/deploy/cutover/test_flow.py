"""Cutover happy-path and rebuild coverage."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from raft.errors import OperatorError

from tests.shared.nginx import NginxEmerg

from .base import CutoverTestCase
from ....base import write_applied_app
from ....cta_asserts import assert_operator


class TestCutoverFlow(CutoverTestCase):
    def test_full_cutover_happy_path(self) -> None:
        s = self._wired_session()
        with patch("raft.services.deploy.cutover.time.sleep"):
            self._run_snapshot_and_tmp(s)
            self._run_shift_rebuild_cleanup(s)

    def _wired_session(self):
        s = self.session
        s.docker.service_container_id.return_value = "cid"
        s.docker.container_image_ref.return_value = "img:old"
        s.docker.container_image_id.side_effect = ["sha_old", "sha_new"]
        s.docker.router_network.return_value = "net1"
        s.docker.router_can_fetch.return_value = True
        s.http.public_host_ok.return_value = True
        return s

    def _run_snapshot_and_tmp(self, s) -> None:
        s.snapshot_previous_image()
        assert s.previous_image == "img:old"
        assert (self.tmp_path / "deploy" / "app.image").is_file()
        s.start_tmp_from_previous()
        s.docker.run_tmp.assert_called_once_with(
            name=s.app.tmp_container, alias=s.app.tmp_alias,
            image="img:old", network="net1", env_file=None,
        )
        assert s.tmp_active is True

    def _run_shift_rebuild_cleanup(self, s) -> None:
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
            self.tmp_path, "app",
            extra={
                "envFile": "/home/raft/.raft/app.env",
                "readiness": {"type": "http", "port": "http", "path": "/ping"},
            },
        )
        s = self.session
        s.previous_image = "img:old"
        s.network = "net1"
        s.docker.router_can_fetch.return_value = True
        with patch("raft.services.deploy.cutover.time.sleep"):
            s.start_tmp_from_previous()
        s.docker.run_tmp.assert_called_once_with(
            name=s.app.tmp_container, alias=s.app.tmp_alias,
            image="img:old", network="net1", env_file="/home/raft/.raft/app.env",
        )
        s.docker.router_can_fetch.assert_called_with(s.app.tmp_alias, port=80, path="/ping")

    def test_rebuild_stable_docker_pulls(self) -> None:
        session = self.docker_session(ref_text="digest\n# requested: abc123\n")
        session.rebuild_stable_service()
        session.docker.recreate_pulled_service.assert_called_once_with(
            session.app, pull_ref="ghcr.io/org/hub:abc123"
        )
        session.docker.rebuild_service.assert_not_called()

    def test_rebuild_stable_docker_defaults_ref(self) -> None:
        session = self.docker_session()
        session.rebuild_stable_service()
        session.docker.recreate_pulled_service.assert_called_once_with(
            session.app, pull_ref="ghcr.io/org/hub:main"
        )

    def test_rebuild_stable_docker_empty_requested_keeps_ref(self) -> None:
        session = self.docker_session(ref_text="digest\n# requested:   \n")
        session.rebuild_stable_service()
        session.docker.recreate_pulled_service.assert_called_once_with(
            session.app, pull_ref="ghcr.io/org/hub:main"
        )

    def test_rebuild_stable_docker_state_without_requested(self) -> None:
        session = self.docker_session(ref_text="sha256:only\n# pin: ghcr.io/org/hub:main\n")
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
            "--- raft-app_tmp (container) ---\nError: OAUTH_CLIENT_ID is required"
        )
        with patch("raft.services.deploy.cutover.time.sleep"):
            with pytest.raises(OperatorError) as caught:
                s.start_tmp_from_previous()

        assert_operator(
            caught.value,
            contains=("app_tmp", "OAUTH_CLIENT_ID"),
        )
        kwargs = s.docker.diagnostics_for.call_args.kwargs
        assert s.app.tmp_container in kwargs.get("containers", ())

    def test_rebuild_stable_timeout_uses_app_diagnostics(self) -> None:
        s = self.session
        s.docker.rebuild_service.return_value = None
        s.docker.router_can_fetch.return_value = False
        s.docker.diagnostics_for.return_value = (
            "--- app (running/unhealthy) ---\n" + NginxEmerg.host_not_found("old")
        )
        with patch("raft.services.deploy.cutover.time.sleep"):
            with pytest.raises(RuntimeError, match="host not found"):
                s.rebuild_stable_service()
        s.docker.diagnostics_for.assert_called_with(s.app.compose_id)
