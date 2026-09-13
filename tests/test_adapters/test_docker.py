"""DockerStack helpers (shell mocked)."""

import pytest

from ..base import make_app
from .base import AdapterTestCase


class TestDockerStack(AdapterTestCase):
    @pytest.fixture(autouse=True)
    def _docker_setup(self, _adapter_setup) -> None:
        self.docker = self.docker_stack()

    def test_start_stop_and_running(self) -> None:
        def compose(*args, **kwargs):
            if args[:1] == ("ps",) and "gate" in args:
                return self.ok("cid1\n")
            if args[:1] == ("ps",):
                return self.ok("")
            return self.ok()

        self.shell.compose.side_effect = compose
        assert self.docker.running_services() == ["gate"]
        self.docker.start_stack()
        self.docker.stop_stack()
        self.shell.compose.assert_any_call("up", "-d", "--build", "--remove-orphans")
        self.shell.compose.assert_any_call("down", "--remove-orphans")
        self.shell.docker.assert_called()

    def test_recreate_rebuild(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.docker.recreate_router()
        self.docker.rebuild_service("app")
        self.shell.compose.assert_any_call(
            "up", "-d", "--no-deps", "--force-recreate", "router"
        )
        self.shell.compose.assert_any_call("up", "-d", "--build", "--no-deps", "app")

    def test_recreate_pulled_service_tags_then_up(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.shell.docker.return_value = self.ok()
        app = make_app(
            "hub", source="docker", image="ghcr.io/org/hub", ref="main"
        )
        self.docker.recreate_pulled_service(app, pull_ref="ghcr.io/org/hub:abc")
        self.shell.docker.assert_any_call("pull", "ghcr.io/org/hub:abc")
        self.shell.docker.assert_any_call(
            "tag", "ghcr.io/org/hub:abc", "ghcr.io/org/hub:main"
        )
        self.shell.compose.assert_any_call(
            "up", "-d", "--no-deps", "--no-build", "--force-recreate", "hub"
        )

    def test_recreate_pulled_service_skips_tag_when_pin(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.shell.docker.return_value = self.ok()
        app = make_app(
            "hub", source="docker", image="ghcr.io/org/hub", ref="main"
        )
        self.docker.recreate_pulled_service(app, pull_ref="ghcr.io/org/hub:main")
        self.shell.docker.assert_any_call("pull", "ghcr.io/org/hub:main")
        assert not any(
            c.args[:1] == ("tag",) for c in self.shell.docker.call_args_list
        )

    def test_service_container_id_missing(self) -> None:
        self.shell.compose.return_value = self.ok("  \n")
        with pytest.raises(RuntimeError, match="not running"):
            self.docker.service_container_id("app")

    def test_container_image_ref_named_ok(self) -> None:
        self.shell.docker.side_effect = [
            self.ok("raft-app:latest\n"),
            self.ok("sha256:abc\n"),
        ]
        assert self.docker.container_image_ref("cid") == "raft-app:latest"

    def test_container_image_ref_commits_when_unnamed(self) -> None:
        self.shell.docker.side_effect = [self.ok(""), self.ok()]
        assert (
            self.docker.container_image_ref("abcdefghijklmn")
            == "raft-snapshot:abcdefghijkl"
        )

    def test_container_image_ref_commits_when_named_missing(self) -> None:
        self.shell.docker.side_effect = [
            self.ok("gone:tag\n"),
            self.ok("", returncode=1),
            self.ok(),
        ]
        assert (
            self.docker.container_image_ref("cid1234567890")
            == "raft-snapshot:cid123456789"
        )

    def test_container_image_id_falls_back_to_ref(self) -> None:
        self.shell.docker.side_effect = [
            self.ok("img:tag\n"),
            self.ok("sha256:id\n"),
            self.ok("  \n"),
        ]
        assert self.docker.container_image_id("cid") == "img:tag"

    def test_router_network_first_or_default(self) -> None:
        self.shell.compose.return_value = self.ok("routerid\n")
        self.shell.docker.return_value = self.ok("net_a\nnet_b\n")
        assert self.docker.router_network() == "net_a"
        self.shell.docker.return_value = self.ok("\n")
        assert self.docker.router_network() == "raft_default"

    def test_run_tmp_and_remove(self) -> None:
        self.shell.docker.return_value = self.ok()
        self.docker.run_tmp(name="n", alias="a", image="img", network="net")
        assert self.shell.docker.call_count >= 2

    def test_router_can_fetch_and_nginx_reload(self) -> None:
        self.shell.compose.return_value = self.ok(returncode=0)
        assert self.docker.router_can_fetch("app") is True
        self.shell.compose.return_value = self.ok(returncode=1)
        assert self.docker.router_can_fetch("app") is False
        self.shell.compose.return_value = self.ok()
        self.docker.nginx_test_and_reload()

    def test_router_sees_upstream_target(self) -> None:
        self.shell.compose.return_value = self.ok(returncode=0)
        assert self.docker.router_sees_upstream_target(self.app, "app_tmp") is True
        self.shell.compose.return_value = self.ok(returncode=1)
        assert self.docker.router_sees_upstream_target(self.app, "app_tmp") is False
