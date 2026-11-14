"""Shared gate ``location /`` proxy body with optional ACL include."""

from typing import Optional

from raft.core.lifecycle.render.edge_down_pages import EdgeDownPages

from .nginx_text import AclNginxText

_DEFAULT_READ = "60s"


class AclProxyLocation:
    """Render proxy-to-router location + optional forbidden / edge-down handlers."""

    @staticmethod
    def location_slash(
        *,
        acl_include: str,
        indent: str = "    ",
        read_timeout: str = _DEFAULT_READ,
        send_timeout: Optional[str] = None,
        app_name: Optional[str] = None,
    ) -> str:
        inner = indent + "    "
        send = AclProxyLocation._send_line(inner, send_timeout)
        return AclProxyLocation._slash_block(
            indent, inner, acl_include, read_timeout, send, app_name=app_name
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
        *,
        app_name: Optional[str],
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
            # Force 503 so CDNs pass through origin HTML instead of their 502 page.
            f"{EdgeDownPages.error_page_line(app_name=app_name, indent=inner)}"
            f"{indent}}}\n"
        )

    @staticmethod
    def unavailable_and_forbidden(
        *,
        acl_include: str,
        indent: str = "    ",
        unavailable_alias: Optional[str] = None,
        forbidden_alias: Optional[str] = None,
        maintenance_alias: Optional[str] = None,
        app_name: Optional[str] = None,
    ) -> str:
        emit_forbidden = bool(acl_include) or forbidden_alias is not None
        forbidden = ""
        if emit_forbidden:
            forbidden = AclNginxText.forbidden_location(
                indent=indent, alias=forbidden_alias
            )
        down = AclProxyLocation._down_pages(
            app_name=app_name,
            unavailable_alias=unavailable_alias,
            maintenance_alias=maintenance_alias,
            indent=indent,
        )
        return forbidden + down

    @staticmethod
    def _down_pages(
        *,
        app_name: Optional[str],
        unavailable_alias: Optional[str],
        maintenance_alias: Optional[str],
        indent: str,
    ) -> str:
        if app_name:
            return EdgeDownPages.chooser_and_pages(
                app_name,
                unavailable_alias=unavailable_alias,
                maintenance_alias=maintenance_alias,
                indent=indent,
            )
        return EdgeDownPages.stock_unavailable_only(indent=indent)
