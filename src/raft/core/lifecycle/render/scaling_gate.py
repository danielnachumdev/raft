"""Gate nginx Host blocks for apps with ``spec.scaling`` (holding page + wake)."""

from pathlib import Path
from typing import Optional

from raft.core.lifecycle.acme.paths import AcmePaths
from raft.core.core.config.settings.types import EdgeConfig
from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec
from .edge.fragments import EdgeFragments
from .scaling_locations import ScalingGateLocations


class ScalingGate:
    """Emit Host-specific gate servers that idle-stop via markers + wake API."""

    def __init__(self) -> None:
        self._locations = ScalingGateLocations()

    def contribute_http(
        self,
        app: App,
        spec: AppSpec,
        *,
        edge: EdgeConfig,
        data_home: Optional[Path] = None,
        acl_include: str = "",
    ) -> EdgeFragments:
        if spec.scaling is None or not app.public_host:
            return EdgeFragments()
        if edge.http is None:
            return EdgeFragments()
        # Live ACME certs: HTTP→HTTPS redirect owns the Host HTTP server.
        if spec.tls == "acme" and data_home is not None:
            if AcmePaths(data_home).live_material_present(app.name):
                return EdgeFragments()
        return EdgeFragments(
            gate_http=[
                self._server_block(
                    app, spec, listen=edge.http, ssl=False, acl_include=acl_include
                )
            ]
        )

    def contribute_tls(self, app: App, spec: AppSpec, *, acl_include: str = "") -> str:
        return self._server_block(
            app, spec, listen=443, ssl=True, acl_include=acl_include
        )

    def _server_block(
        self,
        app: App,
        spec: AppSpec,
        *,
        listen: int,
        ssl: bool,
        acl_include: str = "",
    ) -> str:
        names = " ".join(spec.server_names(app.public_host))
        listen_line = self._listen_line(listen, ssl=ssl)
        certs = self._tls_certs(app, spec) if ssl else ""
        return (
            f"# scaling:{app.name}\n"
            "server {\n"
            f"{listen_line}"
            f"    server_name {names};\n"
            f"{certs}"
            "    resolver 127.0.0.11 valid=10s ipv6=off;\n"
            "\n"
            f"{self._locations.render(app, spec, acl_include=acl_include)}"
            "}\n"
        )

    @staticmethod
    def _listen_line(port: int, *, ssl: bool) -> str:
        if ssl:
            return f"    listen {port} ssl;\n"
        return f"    listen {port};\n"

    @staticmethod
    def _tls_certs(app: App, spec: AppSpec) -> str:
        stem = "acme" if spec.tls == "acme" else "origin"
        return (
            f"    ssl_certificate     /etc/nginx/services/{app.name}/certs/{stem}.pem;\n"
            f"    ssl_certificate_key /etc/nginx/services/{app.name}/certs/{stem}.key;\n"
            "\n"
        )
