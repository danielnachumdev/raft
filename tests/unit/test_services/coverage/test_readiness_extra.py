"""Extra readiness resolve / strategy coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from raft.adapters.docker import DockerStack
from raft.models.ports import PortSpec
from raft.models.readiness_parser import parse_readiness
from raft.models.readiness_spec import ReadinessSpec
from raft.services.readiness import ReadinessStrategy

from ...base import RaftTestCase, make_app, make_stack


class TestReadinessExtraCoverage(RaftTestCase):
    def test_readiness_empty_port_name_and_defaults(self) -> None:
        path = Path("app.yaml")
        ports = (PortSpec(name="http", container_port=80, expose="http"),)
        r = parse_readiness(
            {"readiness": {"type": "http", "port": "  ", "path": ""}},
            ports,
            path,
        )
        assert r.port == "http"
        with pytest.raises(ValueError, match="requires a named port"):
            parse_readiness(
                {"readiness": {"type": "tcp"}},
                (),
                path,
            )
        spec = ReadinessSpec(type="tcp", port=None)
        assert spec.resolve_port(ports).name == "http"

    def test_readiness_http_fallback_and_docker_non_digit(self) -> None:
        self._assert_http_port_fallback()
        self._assert_docker_non_digit_and_tcp()

    def _assert_http_port_fallback(self) -> None:
        ports = (
            PortSpec(name="smtp", container_port=25, expose="stream", public_port=25),
            PortSpec(name="http", container_port=80, expose="http"),
        )
        assert ReadinessSpec(type="http", port=None).resolve_port(ports).name == "http"
        only_stream = (PortSpec(name="smtp", container_port=25, expose="stream", public_port=25),)
        assert ReadinessSpec(type="http", port=None).resolve_port(only_stream).name == "smtp"

    def _assert_docker_non_digit_and_tcp(self) -> None:
        shell = MagicMock()
        docker = DockerStack(make_stack(self.tmp_path), shell)
        shell.compose.return_value = MagicMock(stdout="cid\n", returncode=0)
        shell.docker.return_value = MagicMock(stdout="80/tcp weird\n", returncode=0)
        assert docker.gate_published_ports() == [80]
        app = make_app()
        stack = make_stack(self.tmp_path, (app,))
        http = MagicMock()
        http.tcp_port_ok.return_value = True
        strategy = ReadinessStrategy(
            kind="tcp", port=PortSpec(name="http", container_port=8080, expose="http")
        )
        assert strategy.wait_predicate(app, stack, http)() is True
        http.tcp_port_ok.assert_called_with(8080)

