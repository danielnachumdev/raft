"""Shared gate ``location /`` proxy body with optional ACL include."""

from typing import Optional

from raft.core.lifecycle.render.edge_html_pages import DEFAULT_UNAVAILABLE_ROOT

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
        send = AclProxyLocation._send_line(inner, send_timeout)
        return AclProxyLocation._slash_block(
            indent, inner, acl_include, read_timeout, send
        )

    @staticmethod
    def _send_line(inner: str, send_timeout: Optional[str]) -> str:
        if not send_timeout:
            return ""
        return f"{inner}proxy_send_timeout {send_timeout};\n"

    @staticmethod
    def _slash_block(
        indent: str,
        inner: str,
        acl_include: str,
        read_timeout: str,
        send: str,
    ) -> str:
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
            # Force 503 so CDNs (e.g. Cloudflare) pass through unavailable.html
            # instead of replacing origin 502 bodies with their own error page.
            f"{inner}error_page 502 503 504 =503 /unavailable.html;\n"
            f"{indent}}}\n"
        )

    @staticmethod
    def unavailable_and_forbidden(
        *,
        acl_include: str,
        indent: str = "    ",
        unavailable_alias: Optional[str] = None,
        forbidden_alias: Optional[str] = None,
    ) -> str:
        emit_forbidden = bool(acl_include) or forbidden_alias is not None
        forbidden = ""
        if emit_forbidden:
            forbidden = AclNginxText.forbidden_location(
                indent=indent, alias=forbidden_alias
            )
        return forbidden + AclProxyLocation._unavailable_location(
            indent=indent, alias=unavailable_alias
        )

    @staticmethod
    def _unavailable_location(*, indent: str, alias: Optional[str]) -> str:
        if alias:
            return (
                f"{indent}location = /unavailable.html {{\n"
                f"{indent}    internal;\n"
                f"{indent}    default_type text/html;\n"
                f"{indent}    alias {alias};\n"
                f"{indent}}}\n"
            )
        return (
            f"{indent}location = /unavailable.html {{\n"
            f"{indent}    internal;\n"
            f"{indent}    root {DEFAULT_UNAVAILABLE_ROOT};\n"
            f"{indent}}}\n"
        )
