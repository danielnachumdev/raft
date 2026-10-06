"""Gate nginx Host blocks for apps with ``spec.scaling`` (holding page + wake)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from raft.services.acme.paths import AcmePaths

from ...config.settings_types import EdgeConfig
from ...models.app import App
from ...models.manifest import AppSpec
from .edge.fragments import EdgeFragments

CONTROLLER_WAKE_UPSTREAM = "http://raft-controller:8090"
MARKERS_DIR = "/etc/nginx/scaling/markers"


class ScalingGate:
    """Emit Host-specific gate servers that idle-stop via markers + wake API."""

    def contribute_http(
        self,
        app: App,
        spec: AppSpec,
        *,
        edge: EdgeConfig,
        data_home: Optional[Path] = None,
    ) -> EdgeFragments:
        if spec.scaling is None or not app.public_host:
            return EdgeFragments()
        if edge.http is None:
            return EdgeFragments()
        # Live ACME certs: HTTP→HTTPS redirect owns the Host HTTP server.
        if spec.tls == "acme" and data_home is not None:
            if AcmePaths(data_home).live_material_present(app.name):
                return EdgeFragments()
        return EdgeFragments(gate_http=[self._server_block(app, spec, listen=edge.http, ssl=False)])
    def contribute_tls(self, app: App, spec: AppSpec) -> str:
        return self._server_block(app, spec, listen=443, ssl=True)

    def _server_block(self, app: App, spec: AppSpec, *, listen: int, ssl: bool) -> str:
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
            f"{self._locations(app)}"
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
            f"    ssl_certificate     /etc/nginx/certs/{app.name}/{stem}.pem;\n"
            f"    ssl_certificate_key /etc/nginx/certs/{app.name}/{stem}.key;\n"
            "\n"
        )

    def _locations(self, app: App) -> str:
        zero = f"{MARKERS_DIR}/{app.name}.zero"
        timeout = f"{MARKERS_DIR}/{app.name}.timeout"
        return (
            self._acme_challenge_include()
            + self._proxy_location(app, zero, timeout)
            + self._internal_mirrors(app)
            + self._holding_locations(app)
        )

    @staticmethod
    def _acme_challenge_include() -> str:
        return "    include /etc/nginx/gate/acme_challenge.inc;\n\n"

    def _proxy_location(self, app: App, zero: str, timeout: str) -> str:
        return self._live_location(app, zero, timeout)

    def _live_location(self, app: App, zero: str, timeout: str) -> str:
        hold = f"/_raft_hold_{app.name}"
        timed = f"/_raft_timeout_{app.name}"
        # Prefer holding (``.zero``) over timeout so a scaled app always wakes
        # on a fresh hit when both markers somehow exist; exclusive sync normally
        # keeps only one marker at a time.
        head = (
            "    location / {\n"
            f"        if (-f {zero}) {{ rewrite ^ {hold} last; }}\n"
            f"        if (-f {timeout}) {{ rewrite ^ {timed} last; }}\n"
            f"        mirror /_raft_activity_{app.name};\n"
            "        mirror_request_body off;\n"
        )
        return head + self._proxy_headers() + "    }\n\n"

    @staticmethod
    def _proxy_headers() -> str:
        return (
            "        set $router_upstream http://raft-router:80;\n"
            "        proxy_pass $router_upstream;\n"
            "        proxy_http_version 1.1;\n"
            "        proxy_set_header Host $host;\n"
            "        proxy_set_header X-Real-IP $remote_addr;\n"
            "        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
            "        proxy_set_header X-Forwarded-Proto $scheme;\n"
            "        proxy_connect_timeout 3s;\n"
            "        proxy_read_timeout 60s;\n"
            "        proxy_intercept_errors on;\n"
            "        error_page 502 503 504 /offline.html;\n"
        )

    @staticmethod
    def _holding_locations(app: App) -> str:
        hold = f"/_raft_hold_{app.name}"
        timed = f"/_raft_timeout_{app.name}"
        wake = f"/_raft_wake_{app.name}"
        return (
            ScalingGate._static_mirror_page(hold, wake, "holding.html")
            + ScalingGate._static_mirror_page(
                timed, wake, "holding-timeout.html", ssi=True
            )
            + ScalingGate._timeout_diag_location(app)
            + ScalingGate._offline_location()
        )

    @staticmethod
    def _static_mirror_page(
        location: str, wake: str, page: str, *, ssi: bool = False
    ) -> str:
        # Mirror wake on holding and timeout so refresh / Try again never dead-ends.
        extras = ""
        if ssi:
            extras = "        ssi on;\n        ssi_silent_errors on;\n"
        return (
            f"    location = {location} {{\n"
            f"        mirror {wake};\n"
            "        mirror_request_body off;\n"
            f"{extras}"
            "        default_type text/html;\n"
            f"        alias /usr/share/nginx/errors/{page};\n"
            "    }\n"
            "\n"
        )

    @staticmethod
    def _timeout_diag_location(app: App) -> str:
        path = f"{MARKERS_DIR}/{app.name}.id"
        return (
            "    location = /_raft_timeout_diag {\n"
            "        internal;\n"
            "        default_type text/plain;\n"
            f"        alias {path};\n"
            "    }\n"
            "\n"
        )

    @staticmethod
    def _offline_location() -> str:
        return (
            "    location = /offline.html {\n"
            "        internal;\n"
            "        root /usr/share/nginx/errors;\n"
            "    }\n"
        )

    @staticmethod
    def _internal_mirrors(app: App) -> str:
        base = CONTROLLER_WAKE_UPSTREAM
        return (
            f"    location = /_raft_activity_{app.name} {{\n"
            "        internal;\n"
            f"        proxy_pass {base}/activity/{app.name};\n"
            "        proxy_pass_request_body off;\n"
            '        proxy_set_header Content-Length "";\n'
            "    }\n"
            "\n"
            f"    location = /_raft_wake_{app.name} {{\n"
            "        internal;\n"
            f"        proxy_pass {base}/wake/{app.name};\n"
            "        proxy_pass_request_body off;\n"
            '        proxy_set_header Content-Length "";\n'
            "    }\n"
            "\n"
        )
