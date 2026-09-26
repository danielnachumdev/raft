"""Gate/router nginx reload coverage."""

from unittest.mock import patch

import pytest

from raft.models.ports import PortSpec
from raft.services.ops.certs import MissingOriginCerts

from ...base import make_app
from .base import DockerTestCase


class TestDockerNginxReload(DockerTestCase):
    def test_router_can_fetch_and_nginx_reload(self) -> None:
        self._test_router_can_fetch_and_nginx_reload_p1()
        self._test_router_can_fetch_and_nginx_reload_p2()

    def _test_router_can_fetch_and_nginx_reload_p1(self) -> None:
        self.shell.compose.return_value = self.ok(returncode=0)
        assert self.docker.router_can_fetch("app") is True
        self.shell.compose.return_value = self.ok(returncode=1)
        assert self.docker.router_can_fetch("app") is False
        self.shell.compose.return_value = self.ok()
        assert self.docker.router_can_fetch("app", path="/ping") is True
        self.shell.compose.assert_any_call(
            "exec",
            "-T",
            "raft-router",
            "wget",
            "-qO-",
            "http://app:80/ping",
            check=False,
            capture=True,
        )
        self.shell.compose.return_value = self.ok()
        self.docker.nginx_test_and_reload()

    def _test_router_can_fetch_and_nginx_reload_p2(self) -> None:
        self.shell.compose.assert_any_call(
            "exec", "-T", "raft-router", "nginx", "-t", capture=True, check=False
        )
        self.shell.compose.assert_any_call(
            "exec",
            "-T",
            "raft-router",
            "nginx",
            "-s",
            "reload",
            capture=True,
            check=False,
        )

    def test_reload_gate_nginx(self) -> None:
        self.shell.compose.return_value = self.ok()
        self.docker.reload_gate_nginx()
        self.shell.compose.assert_any_call(
            "exec", "-T", "raft-gate", "nginx", "-t", capture=True, check=False
        )
        self.shell.compose.assert_any_call(
            "exec",
            "-T",
            "raft-gate",
            "nginx",
            "-s",
            "reload",
            capture=True,
            check=False,
        )

    def test_reload_gate_nginx_captures_cert_failure(self) -> None:
        self.shell.compose.return_value = self.ok(
            returncode=1,
            stderr='cannot load certificate "/etc/nginx/certs/web/origin.pem"',
        )
        with pytest.raises(RuntimeError, match="could not load Origin TLS certificates"):
            self.docker.reload_gate_nginx()

    def test_reload_gate_nginx_lists_missing_certs(self) -> None:
        self.shell.compose.return_value = self.ok(
            returncode=1,
            stderr='cannot load certificate "/etc/nginx/certs/web/origin.pem"',
        )
        missing = [MissingOriginCerts("web", ("origin.pem",))]
        with patch(
            "raft.adapters.docker.edge.missing_origin_certs",
            return_value=missing,
        ):
            with pytest.raises(RuntimeError, match="Origin certs missing"):
                self.docker.reload_gate_nginx()

    def test_reload_router_nginx_rejects_bad_config(self) -> None:
        self.shell.compose.return_value = self.ok(returncode=1, stderr="syntax error")
        with pytest.raises(RuntimeError, match="router nginx rejected"):
            self.docker.reload_router_nginx()

    def test_reload_gate_nginx_rejects_non_cert_error(self) -> None:
        self.shell.compose.return_value = self.ok(returncode=1, stderr="unknown directive")
        with pytest.raises(RuntimeError, match="gate nginx rejected"):
            self.docker.reload_gate_nginx()

    def test_reload_router_nginx_reload_failure(self) -> None:
        self.shell.compose.side_effect = [
            self.ok(),  # nginx -t
            self.ok(returncode=1, stderr="reload failed"),
        ]
        with pytest.raises(RuntimeError, match="reload failed"):
            self.docker.reload_router_nginx()

    def test_service_container_id_compose_failure(self) -> None:
        self.shell.compose.return_value = self.ok(
            returncode=1, stderr="Cannot connect to the Docker daemon"
        )
        with pytest.raises(RuntimeError, match="Docker daemon"):
            self.docker.service_container_id("app")

    def test_container_image_ref_commit_failure(self) -> None:
        self.shell.docker.side_effect = [
            self.ok(returncode=1, stderr="Cannot connect to the Docker daemon"),
            self.ok(returncode=1, stderr="commit failed"),
        ]
        with pytest.raises(RuntimeError, match="snapshot running container"):
            self.docker.container_image_ref("cid1234567890")

    def test_router_network_inspect_failure(self) -> None:
        self.shell.compose.return_value = self.ok("routerid\n")
        self.shell.docker.return_value = self.ok(
            returncode=1, stderr="Cannot connect to the Docker daemon"
        )
        with pytest.raises(RuntimeError, match="Docker daemon"):
            self.docker.router_network()

    def test_reload_nginx_empty_detail_and_gate_reload_fail(self) -> None:
        self.shell.compose.return_value = self.ok(returncode=1, stderr="")
        with pytest.raises(RuntimeError, match="router nginx rejected"):
            self.docker.reload_router_nginx()
        with pytest.raises(RuntimeError, match="gate nginx rejected"):
            self.docker.reload_gate_nginx()

        self.shell.compose.side_effect = [
            self.ok(),  # -t ok
            self.ok(returncode=1, stderr=""),  # reload fail empty
        ]
        with pytest.raises(RuntimeError, match="gate recreate"):
            self.docker.reload_gate_nginx()

    def test_router_sees_upstream_target(self) -> None:
        port = PortSpec(name="http", container_port=80, expose="http")
        self.shell.compose.return_value = self.ok(returncode=0)
        assert self.docker.router_sees_upstream_target(self.app, "app_tmp", port) is True
        self.shell.compose.return_value = self.ok(returncode=1)
        assert self.docker.router_sees_upstream_target(self.app, "app_tmp", port) is False

    def test_recreate_gate_and_published_ports(self) -> None:
        self.shell.compose.return_value = self.ok("gatecid\n")
        self.docker.recreate_gate()
        self.shell.compose.assert_any_call(
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "raft-gate",
            capture=False,
            check=False,
        )
        self.shell.docker.return_value = self.ok("80/tcp 443/tcp\n")
        assert self.docker.gate_published_ports() == [80, 443]
        self.shell.compose.return_value = self.ok("  \n")
        assert self.docker.gate_published_ports() == []
