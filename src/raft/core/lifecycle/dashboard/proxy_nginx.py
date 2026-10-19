"""In-container nginx config: auth reverse-proxy in front of the SPA."""

from pathlib import Path

from raft.core.core.config.settings.dashboard_config import DashboardConfig

# Baked into the dashboard image; share path used when generating outside Docker.
IMAGE_LOGIN_HTML = Path("/opt/dashboard/login.html")
DEFAULT_APP_PORT = 18787


class DashboardProxyNginx:
    """Render a full nginx.conf that only proxies to the app when authorized."""

    def render(
        self,
        cfg: DashboardConfig,
        *,
        listen: int,
        app_port: int = DEFAULT_APP_PORT,
        login_html: Path = IMAGE_LOGIN_HTML,
    ) -> str:
        mode = cfg.auth.mode
        if mode == "password":
            server = self._password(listen=listen, app_port=app_port, login=login_html)
        elif mode == "external":
            server = self._external(cfg, listen=listen, app_port=app_port)
        else:
            server = self._open(listen=listen, app_port=app_port)
        return self._wrap(server)

    @staticmethod
    def _wrap(server_body: str) -> str:
        return (
            "pid /tmp/raft-dashboard-nginx.pid;\n"
            "error_log /dev/stderr warn;\n"
            "worker_processes 1;\n"
            "events { worker_connections 128; }\n"
            "http {\n"
            "    access_log /dev/stdout;\n"
            "    client_body_temp_path /tmp/nginx_client_body;\n"
            "    proxy_temp_path /tmp/nginx_proxy;\n"
            "    fastcgi_temp_path /tmp/nginx_fastcgi;\n"
            "    uwsgi_temp_path /tmp/nginx_uwsgi;\n"
            "    scgi_temp_path /tmp/nginx_scgi;\n"
            f"{server_body}"
            "}\n"
        )

    def _open(self, *, listen: int, app_port: int) -> str:
        return self._server(listen, self._location_slash(app_port, auth=""))

    def _password(self, *, listen: int, app_port: int, login: Path) -> str:
        inner = (
            f"{self._auth_subrequest_app(app_port)}"
            f"{self._login_page(login)}"
            f"{self._public_api(app_port, '/api/dashboard/login')}"
            f"{self._public_api(app_port, '/api/dashboard/logout')}"
            f"{self._location_slash(app_port, auth=self._password_auth())}"
            "        location @raft_dashboard_signin {\n"
            "            return 302 /login;\n"
            "        }\n"
        )
        return self._server(listen, inner)

    def _external(self, cfg: DashboardConfig, *, listen: int, app_port: int) -> str:
        inner = (
            "        resolver 127.0.0.11 valid=10s ipv6=off;\n"
            f"{self._auth_subrequest_url(str(cfg.auth.verify_url))}"
            f"{self._location_slash(app_port, auth=self._external_auth(cfg))}"
            "        location @raft_dashboard_signin {\n"
            f"            return 302 {cfg.auth.sign_in_url};\n"
            "        }\n"
        )
        return self._server(listen, inner)

    @staticmethod
    def _server(listen: int, inner: str) -> str:
        return (
            "    server {\n"
            f"        listen {listen};\n"
            "        server_name _;\n"
            f"{inner}"
            "    }\n"
        )

    def _location_slash(self, app_port: int, *, auth: str) -> str:
        return (
            "        location / {\n"
            f"{auth}"
            f"{self._proxy_pass(app_port)}"
            "        }\n"
        )

    @staticmethod
    def _password_auth() -> str:
        return (
            "            auth_request /_raft_dashboard_auth;\n"
            "            error_page 401 = @raft_dashboard_signin;\n"
        )

    @staticmethod
    def _external_auth(cfg: DashboardConfig) -> str:
        header = cfg.auth.identity_header
        var = header.lower().replace("-", "_")
        return (
            "            auth_request /_raft_dashboard_auth;\n"
            f"            auth_request_set $raft_identity $upstream_http_{var};\n"
            f"            proxy_set_header {header} $raft_identity;\n"
            "            error_page 401 = @raft_dashboard_signin;\n"
        )

    @staticmethod
    def _auth_subrequest_app(app_port: int) -> str:
        return (
            "        location = /_raft_dashboard_auth {\n"
            "            internal;\n"
            f"            proxy_pass http://127.0.0.1:{app_port}/api/dashboard/auth;\n"
            "            proxy_pass_request_body off;\n"
            '            proxy_set_header Content-Length "";\n'
            "            proxy_set_header Cookie $http_cookie;\n"
            "        }\n"
        )

    @staticmethod
    def _auth_subrequest_url(verify_url: str) -> str:
        return (
            "        location = /_raft_dashboard_auth {\n"
            "            internal;\n"
            f"            proxy_pass {verify_url};\n"
            "            proxy_pass_request_body off;\n"
            '            proxy_set_header Content-Length "";\n'
            "            proxy_set_header X-Original-URI $request_uri;\n"
            "            proxy_set_header X-Real-IP $remote_addr;\n"
            "        }\n"
        )

    @staticmethod
    def _login_page(login: Path) -> str:
        return (
            "        location = /login {\n"
            "            default_type text/html;\n"
            f"            alias {login};\n"
            "        }\n"
        )

    def _public_api(self, app_port: int, path: str) -> str:
        return (
            f"        location = {path} {{\n"
            f"{self._proxy_pass(app_port)}"
            "        }\n"
        )

    @staticmethod
    def _proxy_pass(app_port: int) -> str:
        return (
            f"            proxy_pass http://127.0.0.1:{app_port};\n"
            "            proxy_http_version 1.1;\n"
            "            proxy_set_header Host $host;\n"
            "            proxy_set_header X-Real-IP $remote_addr;\n"
            "            proxy_set_header X-Forwarded-For "
            "$proxy_add_x_forwarded_for;\n"
            "            proxy_set_header X-Forwarded-Proto $scheme;\n"
            "            proxy_set_header Cookie $http_cookie;\n"
        )
