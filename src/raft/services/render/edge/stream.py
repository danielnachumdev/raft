"""Gate stream edge handler (``expose: stream``)."""

from __future__ import annotations

from dataclasses import dataclass

from raft.adapters.nginx import NginxUpstreamText
from raft.errors import OperatorError

from ....config.settings_types import EdgeConfig
from ....models.app import App
from ....models.manifest import AppSpec
from ....models.ports import PortSpec
from .fragments import EdgeFragments


@dataclass(frozen=True)
class StreamEdge:
    def contribute(
        self,
        app: App,
        spec: AppSpec,
        port: PortSpec,
        *,
        edge: EdgeConfig,
    ) -> EdgeFragments:
        stream = self._require_declared_stream(app, port, edge)
        upstream = f"{app.name}_{port.name}"
        server = self._stream_server(app, port, upstream)
        return EdgeFragments(
            gate_stream=[f"# {app.name}/{port.name}\n{server}"],
            expose_ports=[port.container_port],
        )

    def _require_declared_stream(self, app: App, port: PortSpec, edge: EdgeConfig):
        declared = edge.declared_stream_ports()
        public = port.public_port
        assert public is not None
        if public not in declared:
            raise OperatorError(
                f"{app.name}: ports[{port.name!r}] publicPort {public} is not "
                f"declared in settings edge.streams "
                f"(known: {sorted(declared) or 'none'}).\n"
                f"Fix: add the port under edge.streams in ~/.raft/settings.yaml, "
                f"then: raft render && raft gate recreate"
            )
        return self._match_stream_protocol(app, port, declared[public])

    @staticmethod
    def _match_stream_protocol(app: App, port: PortSpec, stream):
        if stream.protocol != port.protocol:
            raise OperatorError(
                f"{app.name}: ports[{port.name!r}] protocol {port.protocol!r} "
                f"does not match edge.streams entry {stream.name!r} "
                f"({stream.protocol!r}).\n"
                f"Fix: align protocol in .raft/app.yaml and ~/.raft/settings.yaml, "
                f"then: raft render"
            )
        return stream

    @staticmethod
    def _stream_server(app: App, port: PortSpec, upstream: str) -> str:
        public = port.public_port
        assert public is not None
        listen = f"{public}" if port.protocol == "tcp" else f"{public} udp"
        proxy_proto = "\n    proxy_protocol on;" if port.proxy_protocol else ""
        upstream_block = NginxUpstreamText.block(
            upstream,
            app.compose_id,
            port.container_port,
            managed_header=False,
        )
        return (
            f"{upstream_block}"
            "\n"
            "server {\n"
            f"    listen {listen};{proxy_proto}\n"
            f"    proxy_pass {upstream};\n"
            "}\n"
        )
