"""PortSpec parsing and validation."""

from pathlib import Path

import pytest

from ..base import RaftTestCase
from raft.models.ports import PortSpec, parse_ports, port_by_name


class TestPorts(RaftTestCase):
    def test_parse_http_default_expose(self) -> None:
        ports = parse_ports(
            {"ports": [{"name": "http", "containerPort": 8080}]},
            Path("app.yaml"),
        )
        assert ports[0].expose == "http"
        assert ports[0].container_port == 8080
        assert port_by_name(ports, "http") is ports[0]

    def test_stream_requires_public_port(self) -> None:
        with pytest.raises(ValueError, match="publicPort is required"):
            parse_ports(
                {
                    "ports": [
                        {"name": "smtp", "containerPort": 25, "expose": "stream"}
                    ]
                },
                Path("app.yaml"),
            )

    def test_rejects_legacy_port_key(self) -> None:
        with pytest.raises(ValueError, match="spec.port is not supported"):
            parse_ports(
                {"port": 80, "ports": [{"name": "http", "containerPort": 80}]},
                Path("app.yaml"),
            )

    def test_rejects_duplicate_names(self) -> None:
        with pytest.raises(ValueError, match="duplicate port name"):
            parse_ports(
                {
                    "ports": [
                        {"name": "http", "containerPort": 80},
                        {"name": "http", "containerPort": 8080},
                    ]
                },
                Path("app.yaml"),
            )

    def test_proxy_protocol_only_stream(self) -> None:
        with pytest.raises(ValueError, match="proxyProtocol only applies"):
            PortSpec(
                name="http",
                container_port=80,
                expose="http",
                proxy_protocol=True,
            ).validate(path=Path("x"))

    def test_port_by_name_missing(self) -> None:
        ports = (
            PortSpec(name="http", container_port=80, expose="http"),
        )
        with pytest.raises(KeyError, match="unknown port"):
            port_by_name(ports, "smtp")
