"""nginx location blocks for scale-to-zero holding / wake / activity."""

from raft.core.core.models.app import App
from raft.core.core.models.manifest import AppSpec
from .acl.nginx_text import AclNginxText
from .scaling_holding import ScalingHoldingPages

CONTROLLER_WAKE_UPSTREAM = "http://raft-controller:8090"
MARKERS_DIR = "/etc/nginx/scaling/markers"
DEFAULT_HOLDING_ALIAS = "/usr/share/nginx/errors/holding.html"
DEFAULT_TIMEOUT_ALIAS = "/usr/share/nginx/errors/holding-timeout.html"


class ScalingGateLocations:
    """Compose the location{} tree inside a scaling Host server."""

    def render(self, app: App, spec: AppSpec, *, acl_include: str = "") -> str:
        zero = f"{MARKERS_DIR}/{app.name}.zero"
        timeout = f"{MARKERS_DIR}/{app.name}.timeout"
        return (
            self._acme_challenge_include()
            + self._live_location(app, zero, timeout, acl_include=acl_include)
            + self._internal_mirrors(app)
            + self._holding_locations(app, spec)
            + self._forbidden_location(acl_include)
        )

    @staticmethod
    def _acme_challenge_include() -> str:
        return "    include /etc/nginx/gate/acme_challenge.inc;\n\n"

    def _live_location(
        self, app: App, zero: str, timeout: str, *, acl_include: str
    ) -> str:
        hold = f"/_raft_hold_{app.name}"
        timed = f"/_raft_timeout_{app.name}"
        # Prefer holding (``.zero``) over timeout so a scaled app always wakes
        # on a fresh hit when both markers somehow exist; exclusive sync normally
        # keeps only one marker at a time.
        head = (
            "    location / {\n"
            f"{acl_include}"
            f"        if (-f {zero}) {{ rewrite ^ {hold} last; }}\n"
            f"        if (-f {timeout}) {{ rewrite ^ {timed} last; }}\n"
            f"        mirror /_raft_activity_{app.name};\n"
            "        mirror_request_body off;\n"
        )
        return head + self._proxy_headers() + "    }\n\n"

    @staticmethod
    def _forbidden_location(acl_include: str) -> str:
        if not acl_include:
            return ""
        return AclNginxText.forbidden_location() + "\n"

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

    def _holding_locations(self, app: App, spec: AppSpec) -> str:
        hold = f"/_raft_hold_{app.name}"
        timed = f"/_raft_timeout_{app.name}"
        wake = f"/_raft_wake_{app.name}"
        return (
            self._static_mirror_page(hold, wake, self._holding_alias(app, spec))
            + self._static_mirror_page(timed, wake, DEFAULT_TIMEOUT_ALIAS, ssi=True)
            + self._timeout_diag_location(app)
            + self._offline_location()
        )

    @staticmethod
    def _holding_alias(app: App, spec: AppSpec) -> str:
        if spec.scaling is not None and spec.scaling.holding_page:
            return ScalingHoldingPages.container_alias(app.name)
        return DEFAULT_HOLDING_ALIAS

    @staticmethod
    def _static_mirror_page(
        location: str, wake: str, alias: str, *, ssi: bool = False
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
            f"        alias {alias};\n"
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
