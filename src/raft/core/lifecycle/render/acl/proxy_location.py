"""Shared gate ``location /`` proxy body with optional ACL include."""

from typing import Optional

from .nginx_text import AclNginxText

_DEFAULT_READ = "60s"


class AclProxyLocation:
    """Render proxy-to-router location + optional forbidden handler."""

    @staticmethod
    def location_slash(
        *,
        acl_include: str,
        indent: str = "    ",
        read_timeout: str = _DEFAULT_READ,
        send_timeout: Optional[str] = None,
    ) -> str:
        inner = indent + "    "
        send = ""
        if send_timeout:
            send = f"{inner}proxy_send_timeout {send_timeout};\n"
        return (
            f"{indent}location / {{\n"
            f"{acl_include}"
            f"{inner}set $router_upstream http://raft-router:80;\n"
            f"{inner}proxy_pass $router_upstream;\n"
            f"{inner}proxy_http_version 1.1;\n"
            f"{inner}proxy_set_header Host $host;\n"
            f"{inner}proxy_set_header X-Real-IP $remote_addr;\n"
            f"{inner}proxy_set_header X-Forwarded-For "
            f"$proxy_add_x_forwarded_for;\n"
            f"{inner}proxy_set_header X-Forwarded-Proto $scheme;\n"
            f"{inner}proxy_connect_timeout 3s;\n"
            f"{inner}proxy_read_timeout {read_timeout};\n"
            f"{send}"
            f"{inner}proxy_intercept_errors on;\n"
            f"{inner}error_page 502 503 504 /offline.html;\n"
            f"{indent}}}\n"
        )

    @staticmethod
    def offline_and_forbidden(*, acl_include: str, indent: str = "    ") -> str:
        forbidden = AclNginxText.forbidden_location(indent=indent) if acl_include else ""
        return (
            f"{forbidden}"
            f"{indent}location = /offline.html {{\n"
            f"{indent}    internal;\n"
            f"{indent}    root /usr/share/nginx/errors;\n"
            f"{indent}}}\n"
        )
