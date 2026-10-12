"""Canonical nginx ``upstream { … }`` snippet body (render + live cutover)."""


class NginxUpstreamText:
    """Build ``upstream`` blocks; park absent hosts on loopback for nginx -t."""

    # Static ``server hostname:port`` fails nginx -t when the Compose DNS name
    # is absent (scaled-to-zero). Park those upstreams on loopback so router
    # can start/reload; gate holding pages handle visitor traffic.
    ABSENT_HOSTNAME = "127.0.0.1"

    @classmethod
    def hostname_for(cls, compose_id: str, *, absent: bool) -> str:
        return cls.ABSENT_HOSTNAME if absent else compose_id

    @staticmethod
    def block(
        name: str,
        hostname: str,
        container_port: int,
        *,
        managed_header: bool = True,
    ) -> str:
        body = f"upstream {name} {{\n" f"    server {hostname}:{container_port};\n" "}\n"
        if not managed_header:
            return body
        return "# Managed by raft — do not hand-edit while deploying.\n" + body
