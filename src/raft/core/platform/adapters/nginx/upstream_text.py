"""Canonical nginx ``upstream { … }`` snippet body (render + live cutover)."""


class NginxUpstreamText:
    """Build ``upstream`` blocks; park absent hosts for nginx -t / reload."""

    # Compose DNS names fail nginx -t when the service is absent (scaled-to-zero /
    # inplace stop). Park on loopback marked ``down`` so the router never opens a
    # real connection — immediate 502, then gate ``error_page … =503`` serves
    # unavailable.html (503 so CDNs like Cloudflare do not replace the body). A bare
    # ``127.0.0.1:<listen-port>`` would accept into the router's own ``listen``
    # and self-proxy instead.
    ABSENT_HOSTNAME = "127.0.0.1"

    @classmethod
    def hostname_for(cls, compose_id: str, *, absent: bool) -> str:
        return cls.ABSENT_HOSTNAME if absent else compose_id

    @classmethod
    def server_directive(cls, hostname: str, container_port: int) -> str:
        if hostname == cls.ABSENT_HOSTNAME:
            return f"server {cls.ABSENT_HOSTNAME}:{container_port} down;"
        return f"server {hostname}:{container_port};"

    @classmethod
    def block(
        cls,
        name: str,
        hostname: str,
        container_port: int,
        *,
        managed_header: bool = True,
    ) -> str:
        directive = cls.server_directive(hostname, container_port)
        body = f"upstream {name} {{\n    {directive}\n}}\n"
        if not managed_header:
            return body
        return "# Managed by raft — do not hand-edit while deploying.\n" + body
