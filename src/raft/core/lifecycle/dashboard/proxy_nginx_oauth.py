"""Gate nginx server body for dashboard ``auth.mode: oauth``."""

from pathlib import Path

from raft.core.core.config.settings.dashboard_config import DashboardConfig

from .oauth_paths import OAUTH_PROXY_PORT
from .proxy_nginx import DashboardProxyNginx

IMAGE_UNAUTHORIZED = Path("/opt/dashboard/unauthorized.html")


class DashboardOAuthNginx:
    """auth_request → oauth2-proxy; SPA only after allowlist success."""

    def server(
        self,
        cfg: DashboardConfig,
        *,
        listen: int,
        app_port: int,
        unauthorized: Path = IMAGE_UNAUTHORIZED,
    ) -> str:
        auth = self._auth_directives(cfg.auth.identity_header)
        inner = (
            f"{self._auth_subrequest()}"
            f"{self._oauth_locations()}"
            f"{self._unauthorized_page(unauthorized)}"
            f"{DashboardProxyNginx()._location_slash(app_port, auth=auth)}"
            f"{self._named_locations()}"
        )
        return DashboardProxyNginx._server(listen, inner)

    @staticmethod
    def _auth_directives(header: str) -> str:
        var = "x_auth_request_email"
        return (
            "            auth_request /_raft_dashboard_auth;\n"
            f"            auth_request_set $raft_identity $upstream_http_{var};\n"
            f"            proxy_set_header {header} $raft_identity;\n"
            "            error_page 401 = @raft_dashboard_signin;\n"
            "            error_page 403 = @raft_dashboard_denied;\n"
        )

    @staticmethod
    def _named_locations() -> str:
        return (
            "        location @raft_dashboard_signin {\n"
            "            return 302 /oauth2/start?rd=$request_uri;\n"
            "        }\n"
            "        location @raft_dashboard_denied {\n"
            "            return 302 /unauthorized;\n"
            "        }\n"
        )

    @staticmethod
    def _auth_subrequest() -> str:
        return (
            "        location = /_raft_dashboard_auth {\n"
            "            internal;\n"
            f"            proxy_pass http://127.0.0.1:{OAUTH_PROXY_PORT}"
            "/oauth2/auth;\n"
            "            proxy_pass_request_body off;\n"
            '            proxy_set_header Content-Length "";\n'
            "            proxy_set_header Host $host;\n"
            "            proxy_set_header X-Real-IP $remote_addr;\n"
            "            proxy_set_header X-Forwarded-Uri $request_uri;\n"
            "            proxy_set_header X-Forwarded-Proto $scheme;\n"
            "        }\n"
        )

    @staticmethod
    def _oauth_locations() -> str:
        return (
            "        location /oauth2/ {\n"
            f"            proxy_pass http://127.0.0.1:{OAUTH_PROXY_PORT};\n"
            "            proxy_set_header Host $host;\n"
            "            proxy_set_header X-Real-IP $remote_addr;\n"
            "            proxy_set_header X-Forwarded-For "
            "$proxy_add_x_forwarded_for;\n"
            "            proxy_set_header X-Forwarded-Proto $scheme;\n"
            "            proxy_set_header X-Auth-Request-Redirect $request_uri;\n"
            "            proxy_intercept_errors on;\n"
            "            error_page 403 = @raft_dashboard_denied;\n"
            "        }\n"
        )

    @staticmethod
    def _unauthorized_page(path: Path) -> str:
        return (
            "        location = /unauthorized {\n"
            "            default_type text/html;\n"
            f"            alias {path};\n"
            "        }\n"
        )
