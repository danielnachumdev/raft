"""Nginx/docker/readiness adapter edge coverage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from raft.adapters.docker import DockerStack
from raft.adapters.nginx import NginxUpstreams
from raft.models.ports import PortSpec
from raft.services.readiness import ReadinessStrategy

from ...base import RaftTestCase, make_app, make_stack


class TestAdapterCoverage(RaftTestCase):
    def test_nginx_fallback_and_docker_ports(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("lonely"),))
        nginx = NginxUpstreams(stack, MagicMock())
        nginx.ensure_steady_file(stack.apps[0])
        assert (stack.upstreams_dir / "lonely-http.conf").is_file()
        shell = MagicMock()
        docker = DockerStack(stack, shell)
        shell.compose.return_value = MagicMock(stdout="cid\n", returncode=0)
        shell.docker.return_value = MagicMock(stdout="", returncode=1)
        assert docker.gate_published_ports() == []
        shell.docker.return_value = MagicMock(stdout="80/tcp\n", returncode=0)
        assert docker.gate_published_ports() == [80]

    def test_readiness_wait_predicates(self) -> None:
        app = make_app()
        stack = make_stack(self.tmp_path, (app,))
        http = MagicMock()
        http.public_host_ok.return_value = True
        http.tcp_port_ok.return_value = True
        self._assert_http_tcp(app, stack, http)
        self._assert_internal_tcp(app, stack, http)
        self._assert_weird_kind(app, stack, http)

    def _assert_http_tcp(self, app, stack, http) -> None:
        strategy = ReadinessStrategy(
            kind="http", port=PortSpec(name="http", container_port=80, expose="http")
        )
        assert strategy.wait_predicate(app, stack, http)() is True
        tcp = ReadinessStrategy(
            kind="tcp",
            port=PortSpec(name="smtp", container_port=25, expose="stream", public_port=25),
        )
        assert tcp.wait_predicate(app, stack, http)() is True
        assert tcp.wait_predicate(app, stack, http, tcp_ok=lambda p: p == 25)() is True

    def _assert_internal_tcp(self, app, stack, http) -> None:
        internal = ReadinessStrategy(
            kind="tcp", port=PortSpec(name="http", container_port=8000, expose="none")
        )
        assert internal.wait_predicate(app, stack, http)() is False
        assert internal.wait_predicate(app, stack, http, compose_ready=lambda: True)() is True
        assert internal.wait_predicate(app, stack, http, tcp_ok=lambda p: p == 8000)() is True

    def _assert_weird_kind(self, app, stack, http) -> None:
        weird = ReadinessStrategy(
            kind="weird", port=PortSpec(name="http", container_port=80, expose="http")
        )
        with pytest.raises(ValueError):
            weird.healthcheck_test()
        with pytest.raises(ValueError):
            weird.wait_predicate(app, stack, http)
