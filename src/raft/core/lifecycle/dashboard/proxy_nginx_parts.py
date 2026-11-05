"""Shared nginx location fragments for dashboard proxy configs."""

from .update_proxy_timeout import UPDATE_PROXY_TIMEOUT


class DashboardNginxParts:
    """Reusable location / server / proxy_pass snippets (no auth-mode policy)."""

    @staticmethod
    def server(listen: int, inner: str) -> str:
        # Relative Location so TLS-terminating edges (gate/CF) keep https/host.
        return (
            "    server {\n"
            f"        listen {listen};\n"
            "        server_name _;\n"
            "        server_tokens off;\n"
            "        absolute_redirect off;\n"
            "        port_in_redirect off;\n"
            f"{inner}"
            "    }\n"
        )

    def location_slash(self, app_port: int, *, auth: str) -> str:
        return (
            "        location / {\n"
            f"{auth}"
            f"{self.proxy_pass(app_port)}"
            "        }\n"
        )

    def location_update(self, app_port: int, *, auth: str) -> str:
        """Longer timeouts for Settings → Update (Docker one-shot + install.sh)."""
        return (
            "        location = /api/update {\n"
            f"{auth}"
            f"{self.proxy_pass(app_port, read_timeout=UPDATE_PROXY_TIMEOUT)}"
            "        }\n"
        )

    @staticmethod
    def proxy_pass(app_port: int, *, read_timeout: str = "60s") -> str:
        return (
            f"            proxy_pass http://127.0.0.1:{app_port};\n"
            "            proxy_http_version 1.1;\n"
            "            proxy_set_header Host $host;\n"
            "            proxy_set_header X-Real-IP $remote_addr;\n"
            "            proxy_set_header X-Forwarded-For "
            "$proxy_add_x_forwarded_for;\n"
            "            proxy_set_header X-Forwarded-Proto $raft_fwd_proto;\n"
            "            proxy_set_header Cookie $http_cookie;\n"
            f"            proxy_read_timeout {read_timeout};\n"
            f"            proxy_send_timeout {read_timeout};\n"
        )
