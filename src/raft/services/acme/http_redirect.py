"""HTTP→HTTPS redirect fragments for ``tls: acme`` when live PEMs exist."""

from __future__ import annotations

from pathlib import Path

from raft.config.settings_types import EdgeConfig
from raft.models.app import App
from raft.models.manifest import AppSpec
from raft.services.acme.paths import AcmePaths
from raft.services.render.edge.fragments import EdgeFragments


class AcmeHttpRedirect:
    """Host-specific gate HTTP servers: challenge carve-out + 301 to HTTPS."""

    def contribute(
        self,
        app: App,
        spec: AppSpec,
        *,
        edge: EdgeConfig,
        data_home: Path,
    ) -> EdgeFragments:
        if spec.tls != "acme" or not app.public_host:
            return EdgeFragments()
        if edge.http is None:
            return EdgeFragments()
        if not AcmePaths(data_home).live_material_present(app.name):
            return EdgeFragments()
        return EdgeFragments(gate_http=[self._server_block(app, spec, listen=edge.http)])

    @staticmethod
    def _server_block(app: App, spec: AppSpec, *, listen: int) -> str:
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
            "        return 301 https://$host$request_uri;\n"
            "    }\n"
            "}\n"
        )
