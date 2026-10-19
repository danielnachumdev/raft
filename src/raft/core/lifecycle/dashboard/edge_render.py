"""Emit gate/router/upstream fragments for public ``raft-dashboard``."""

from pathlib import Path

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.acme.paths import AcmePaths
from raft.core.lifecycle.render.edge.fragments import EdgeFragments
from raft.core.lifecycle.render.edge.tls import TlsEdge
from raft.core.platform.adapters.nginx import NginxUpstreamText

from .edge_auth import DashboardEdgeAuth
from .target import DashboardTarget


class DashboardEdgeRender:
    """First-party Host → upstream (+ TLS / optional auth_request)."""

    def __init__(self) -> None:
        self._target = DashboardTarget()
        self._tls = TlsEdge()
        self._auth = DashboardEdgeAuth()

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
        frag.merge(self._gate_bits(cfg, edge, data_home, acl_include))
        return frag

    def _gate_bits(
        self,
        cfg: DashboardConfig,
        edge: EdgeConfig,
        data_home: Path,
        acl_include: str,
    ) -> EdgeFragments:
        if cfg.auth.mode == "external":
            return self._external_bits(
                cfg, edge=edge, data_home=data_home, acl_include=acl_include
            )
        app = self._target.app(cfg)
        assert app is not None
        return self._tls.contribute_app(
            app,
            self._target.spec(cfg),
            edge=edge,
            data_home=data_home,
            acl_include=acl_include,
        )

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
            f"        proxy_pass http://{upstream};",
            "        proxy_set_header Host $host;",
            "        proxy_set_header X-Real-IP $remote_addr;",
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
            "        proxy_set_header X-Forwarded-Proto $scheme;",
            "        proxy_connect_timeout 3s;",
            "        proxy_read_timeout 60s;",
            "    }",
            "}",
            "",
        ]

    def _external_bits(
        self,
        cfg: DashboardConfig,
        *,
        edge: EdgeConfig,
        data_home: Path,
        acl_include: str,
    ) -> EdgeFragments:
        if cfg.tls in {"origin", "acme"}:
            return self._external_tls(
                cfg, edge=edge, data_home=data_home, acl_include=acl_include
            )
        if edge.http is None:
            raise OperatorError(
                "dashboard external auth with tls=off requires edge.http.\n"
                "Fix: set edge.http: 80 in ~/.raft/settings.yaml",
                has_fix=False,
            )
        body = self._auth.server(cfg, ssl=False, acl_include=acl_include)
        return EdgeFragments(gate_http=[body])

    def _external_tls(
        self,
        cfg: DashboardConfig,
        *,
        edge: EdgeConfig,
        data_home: Path,
        acl_include: str,
    ) -> EdgeFragments:
        app = self._target.app(cfg)
        assert app is not None
        if not self._external_tls_ready(app, cfg, edge, data_home):
            return EdgeFragments()
        body = self._auth.server(cfg, ssl=True, acl_include=acl_include)
        return EdgeFragments(gate_tls={f"{app.name}.conf": body})

    def _external_tls_ready(self, app, cfg, edge, data_home: Path) -> bool:
        if cfg.tls == "acme":
            self._tls.require_acme_edge(app, edge)
            return AcmePaths(data_home).live_material_present(app.name)
        if edge.https is None:
            raise OperatorError(
                f"{app.name}: tls=origin requires edge.https in settings.yaml.\n"
                f"Fix: set edge.https (e.g. 443) in ~/.raft/settings.yaml",
                has_fix=False,
            )
        return True

    @staticmethod
    def _require_password_hash(cfg: DashboardConfig) -> None:
        if cfg.requires_password_hash() and not cfg.auth.password_hash:
            raise OperatorError(
                "dashboard public password auth requires passwordHash.\n"
                "Fix: raft dashboard set-password, then raft render",
                has_fix=False,
            )
