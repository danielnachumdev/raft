"""HTTP→HTTPS redirect nginx snippets for ``tls: acme`` when live PEMs exist."""

from pathlib import Path
from typing import List

from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec
from raft.core.lifecycle.render.acl.nginx_text import AclNginxText
from raft.core.lifecycle.render.edge_html_pages import EdgeHtmlPages
from .paths import AcmePaths


class AcmeHttpRedirect:
    """Host-specific gate HTTP servers: challenge carve-out + 301 to HTTPS."""

    def contribute(
        self,
        app: App,
        spec: AppSpec,
        *,
        edge: EdgeConfig,
        data_home: Path,
        acl_include: str = "",
    ) -> List[str]:
        if spec.tls != "acme" or not app.public_host:
            return []
        if edge.http is None:
            return []
        if not AcmePaths(data_home).live_material_present(app.name):
            return []
        return [
            self._server_block(app, spec, listen=edge.http, acl_include=acl_include)
        ]

    @classmethod
    def _server_block(
        cls, app: App, spec: AppSpec, *, listen: int, acl_include: str = ""
    ) -> str:
        names = " ".join(spec.server_names(app.public_host))
        return (
            f"# acme-redirect:{app.name}\n"
            "server {\n"
            f"    listen {listen};\n"
            f"    server_name {names};\n"
            "\n"
            "    include /etc/nginx/gate/acme_challenge.inc;\n"
            "\n"
            "    location / {\n"
            f"{acl_include}"
            "        return 301 https://$host$request_uri;\n"
            "    }\n"
            f"{cls._forbidden(app, spec, acl_include=acl_include)}"
            "}\n"
        )

    @staticmethod
    def _forbidden(app: App, spec: AppSpec, *, acl_include: str) -> str:
        _, forbid, _ = EdgeHtmlPages.aliases_for(app, spec)
        if not acl_include and forbid is None:
            return ""
        return AclNginxText.forbidden_location(alias=forbid)
