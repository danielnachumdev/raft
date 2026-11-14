"""Host-specific gate HTTP servers for per-app ACL / edge HTML pages."""

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec
from ..edge.fragments import EdgeFragments
from ..edge_html_pages import EdgeHtmlPages
from .proxy_location import AclProxyLocation


class HttpGateHost:
    """Emit a Host gate server that proxies to the router with ACL / edge pages."""

    def contribute(
        self,
        app: App,
        spec: AppSpec,
        *,
        edge: EdgeConfig,
        acl_include: str,
    ) -> EdgeFragments:
        if not app.public_host or edge.http is None:
            return EdgeFragments()
        if not self._needs_host_server(spec, acl_include=acl_include):
            return EdgeFragments()
        if not any(port.expose == "http" for port in spec.ports):
            return EdgeFragments()
        return EdgeFragments(
            gate_http=[
                self._server_block(app, spec, listen=edge.http, acl_include=acl_include)
            ]
        )

    @staticmethod
    def _needs_host_server(spec: AppSpec, *, acl_include: str) -> bool:
        if acl_include:
            return True
        return bool(spec.unavailable_page or spec.forbidden_page)

    def _server_block(
        self, app: App, spec: AppSpec, *, listen: int, acl_include: str
    ) -> str:
        names = " ".join(spec.server_names(app.public_host))
        return (
            f"# acl-host:{app.name}\n"
            "server {\n"
            f"    listen {listen};\n"
            f"    server_name {names};\n"
            "    resolver 127.0.0.11 valid=10s ipv6=off;\n"
            "\n"
            "    include /etc/nginx/gate/acme_challenge.inc;\n"
            "\n"
            f"{self._locations(app, spec, acl_include=acl_include)}"
            "}\n"
        )

    @staticmethod
    def _locations(app: App, spec: AppSpec, *, acl_include: str) -> str:
        unavail, forbid = EdgeHtmlPages.aliases_for(app, spec)
        pages = AclProxyLocation.unavailable_and_forbidden(
            acl_include=acl_include,
            unavailable_alias=unavail,
            forbidden_alias=forbid,
        )
        return (
            f"{AclProxyLocation.location_slash(acl_include=acl_include)}"
            "\n"
            f"{pages}"
        )
