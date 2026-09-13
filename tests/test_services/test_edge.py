"""Edge handlers and readiness strategy."""

from pathlib import Path

import pytest

from ..base import RaftTestCase, make_app
from raft.config.settings import EdgeConfig, EdgeStream
from raft.models.manifest import AppSpec
from raft.models.ports import PortSpec
from raft.models.readiness import ReadinessSpec
from raft.services.edge import (
    HostEdge,
    HttpEdge,
    StreamEdge,
    TlsEdge,
    handler_for,
)
from raft.services.readiness import ReadinessStrategy
from unittest.mock import MagicMock


class TestEdgeHandlers(RaftTestCase):
    def test_http_edge(self) -> None:
        app = make_app("web", public_host="web.example.com")
        spec = AppSpec(
            ports=(PortSpec(name="http", container_port=80, expose="http"),),
        )
        frag = HttpEdge().contribute(
            app, spec, spec.ports[0], edge=EdgeConfig()
        )
        assert "web-http.conf" in frag.upstreams
        assert any("server_name web.example.com" in line for line in frag.router_servers)

    def test_tls_edge_requires_https(self) -> None:
        app = make_app("web", public_host="web.example.com")
        spec = AppSpec(
            ports=(PortSpec(name="http", container_port=80, expose="http"),),
            tls="origin",
        )
        with pytest.raises(ValueError, match="edge.https"):
            TlsEdge().contribute_app(app, spec, edge=EdgeConfig(https=None))
        frag = TlsEdge().contribute_app(app, spec, edge=EdgeConfig())
        assert "web.conf" in frag.gate_tls

    def test_stream_edge_undeclared(self) -> None:
        app = make_app("mail", public_host="mail.example.com")
        port = PortSpec(
            name="smtp",
            container_port=25,
            expose="stream",
            public_port=25,
        )
        spec = AppSpec(ports=(port,))
        with pytest.raises(ValueError, match="not declared"):
            StreamEdge().contribute(app, spec, port, edge=EdgeConfig())

    def test_stream_and_host(self) -> None:
        app = make_app("mail", public_host="mail.example.com")
        smtp = PortSpec(
            name="smtp",
            container_port=25,
            expose="stream",
            public_port=25,
            proxy_protocol=True,
        )
        sub = PortSpec(
            name="submission",
            container_port=587,
            expose="host",
            public_port=587,
        )
        spec = AppSpec(ports=(smtp, sub))
        edge = EdgeConfig(
            streams=(EdgeStream(name="smtp", port=25, protocol="tcp"),)
        )
        stream_frag = StreamEdge().contribute(app, spec, smtp, edge=edge)
        assert "proxy_protocol on" in stream_frag.gate_stream[0]
        host_frag = HostEdge().contribute(app, spec, sub, edge=edge)
        assert '"587:587"' in host_frag.host_publish

    def test_handler_for(self) -> None:
        assert handler_for("http") is not None
        with pytest.raises(KeyError):
            handler_for("bogus")


class TestReadinessStrategy(RaftTestCase):
    def test_http_and_tcp_and_none(self) -> None:
        http = AppSpec(
            ports=(PortSpec(name="http", container_port=80, expose="http"),),
            readiness=ReadinessSpec(type="http", port="http", path="/ready"),
        )
        s = ReadinessStrategy.from_spec(http)
        assert s.healthcheck_test()[1] == "wget"
        assert "/ready" in s.healthcheck_test()[-1]

        tcp = AppSpec(
            ports=(
                PortSpec(
                    name="smtp",
                    container_port=25,
                    expose="stream",
                    public_port=25,
                ),
            ),
            readiness=ReadinessSpec(type="tcp", port="smtp"),
        )
        t = ReadinessStrategy.from_spec(tcp)
        assert t.healthcheck_test()[0] == "CMD-SHELL"
        assert "nc -z" in t.healthcheck_test()[1]

        none = AppSpec(
            ports=(PortSpec(name="http", container_port=80, expose="http"),),
            readiness=ReadinessSpec(type="none"),
        )
        assert ReadinessStrategy.from_spec(none).healthcheck_test() is None
        assert (
            ReadinessStrategy.from_spec(none).wait_predicate(
                make_app(), self.local_stack(), MagicMock()
            )
            is None
        )
