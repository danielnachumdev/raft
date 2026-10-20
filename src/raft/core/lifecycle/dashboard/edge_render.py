"""Emit gate/router/upstream fragments for public ``raft-dashboard``."""

from pathlib import Path

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.render.edge.fragments import EdgeFragments
from raft.core.lifecycle.render.edge.tls import TlsEdge
from raft.core.platform.adapters.nginx import NginxUpstreamText

from .target import DashboardTarget


class DashboardEdgeRender:
    """Host → upstream like any App; auth is inside the dashboard container."""

    def __init__(self) -> None:
        self._target = DashboardTarget()
        self._tls = TlsEdge()

    def contribute(
        self,
        cfg: DashboardConfig,
        *,
        edge: EdgeConfig,
        data_home: Path,
        acl_include: str = "",
    ) -> EdgeFragments:
        if self._target.app(cfg) is None:
            return EdgeFragments()
        self._require_password_hash(cfg)
        frag = self._http_upstream(cfg)
        app = self._target.app(cfg)
        assert app is not None
        frag.merge(
            self._tls.contribute_app(
                app,
                self._target.spec(cfg),
                edge=edge,
                data_home=data_home,
                acl_include=acl_include,
            )
        )
        return frag

    def _http_upstream(self, cfg: DashboardConfig) -> EdgeFragments:
        name = DashboardTarget.SERVICE_NAME
        filename = f"{name}-http.conf"
        upstream = f"{name}_http"
        return EdgeFragments(
            router_includes=[f"include /etc/nginx/upstreams/{filename};"],
            router_servers=self._router_server(cfg, upstream),
            upstreams={
                filename: NginxUpstreamText.block(upstream, name, cfg.port),
            },
        )

    def _router_server(self, cfg: DashboardConfig, upstream: str) -> list[str]:
        host = str(cfg.public_host).strip()
        return [
            "server {",
            "    listen 80;",
            f"    server_name {host};",
            "",
            "    location / {",
            *self._proxy_lines(upstream),
            "    }",
            "}",
            "",
        ]

    @staticmethod
    def _proxy_lines(upstream: str) -> list[str]:
        # 600s: Settings → Update may pull a one-shot image + run install.sh.
        # X-Forwarded-Proto: preserve gate TLS for in-container oauth2-proxy.
        return [
            f"        proxy_pass http://{upstream};",
            "        proxy_set_header Host $host;",
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;",
            "        proxy_connect_timeout 3s;",
            "        proxy_read_timeout 600s;",
            "        proxy_send_timeout 600s;",
        ]

    @staticmethod
    def _require_password_hash(cfg: DashboardConfig) -> None:
        if cfg.requires_password_hash() and not cfg.auth.password_hash:
            raise OperatorError(
                "dashboard public password auth requires passwordHash.\n"
                "Fix: raft dashboard set-password, then raft render",
                has_fix=False,
            )
