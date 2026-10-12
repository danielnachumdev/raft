"""HTTP Host-routing edge handler (``expose: http``)."""

from dataclasses import dataclass

from raft.core.platform.adapters.nginx import NginxUpstreamText
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec
from raft.core.core.models.ports import PortSpec
from ..fragments import EdgeFragments


@dataclass(frozen=True)
class HttpEdge:
    def contribute(
        self,
        app: App,
        spec: AppSpec,
        port: PortSpec,
        *,
        edge: EdgeConfig,
    ) -> EdgeFragments:
        upstream = f"{app.name}_{port.name}"
        filename = f"{app.name}-{port.name}.conf"
        return EdgeFragments(
            router_includes=[f"include /etc/nginx/upstreams/{filename};"],
            router_servers=self._server_block(app, spec, upstream),
            upstreams={
                filename: NginxUpstreamText.block(
                    upstream, app.compose_id, port.container_port
                )
            },
            expose_ports=[port.container_port],
        )

    @staticmethod
    def _server_block(app: App, spec: AppSpec, upstream: str) -> list[str]:
        names = " ".join(spec.server_names(app.public_host))
        return [
            "server {",
            "    listen 80;",
            f"    server_name {names};",
            "",
            "    location / {",
            f"        proxy_pass http://{upstream};",
            "        proxy_set_header Host $host;",
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "        proxy_set_header X-Forwarded-Proto $scheme;",
            "        proxy_connect_timeout 3s;",
            "        proxy_read_timeout 30s;",
            "    }",
            "}",
            "",
        ]
