"""Per-Host nginx locations: unavailable vs maintenance from redeploy marker."""

from typing import Optional

from raft.core.core.models.state.redeploying_store import RedeployingStore
from raft.core.lifecycle.render.edge_html_pages import DEFAULT_UNAVAILABLE_ROOT

CHOOSER_URI = "/_raft_edge_down"
DEFAULT_MAINTENANCE_ALIAS = "/usr/share/nginx/errors/maintenance.html"


class EdgeDownPages:
    """502/503/504 → chooser → maintenance.html (marker) or unavailable.html."""

    @classmethod
    def error_page_target(cls, *, app_name: Optional[str]) -> str:
        return CHOOSER_URI if app_name else "/unavailable.html"

    @classmethod
    def error_page_line(cls, *, app_name: Optional[str], indent: str = "        ") -> str:
        target = cls.error_page_target(app_name=app_name)
        return f"{indent}error_page 502 503 504 =503 {target};\n"

    @classmethod
    def chooser_and_pages(
        cls,
        app_name: str,
        *,
        unavailable_alias: Optional[str] = None,
        maintenance_alias: Optional[str] = None,
        indent: str = "    ",
    ) -> str:
        return (
            cls._chooser(app_name, indent=indent)
            + cls._page_location(
                "/unavailable.html",
                alias=unavailable_alias,
                stock_root=DEFAULT_UNAVAILABLE_ROOT,
                indent=indent,
            )
            + cls._page_location(
                "/maintenance.html",
                alias=maintenance_alias,
                stock_alias=DEFAULT_MAINTENANCE_ALIAS,
                indent=indent,
            )
        )

    @classmethod
    def stock_unavailable_only(cls, *, indent: str = "    ") -> str:
        return cls._page_location(
            "/unavailable.html",
            alias=None,
            stock_root=DEFAULT_UNAVAILABLE_ROOT,
            indent=indent,
        )

    @staticmethod
    def _chooser(app_name: str, *, indent: str) -> str:
        marker = RedeployingStore.container_marker(app_name)
        inner = indent + "    "
        return (
            f"{indent}location = {CHOOSER_URI} {{\n"
            f"{inner}internal;\n"
            f"{inner}if (-f {marker}) {{ rewrite ^ /maintenance.html last; }}\n"
            f"{inner}rewrite ^ /unavailable.html last;\n"
            f"{indent}}}\n"
        )

    @staticmethod
    def _page_location(
        uri: str,
        *,
        alias: Optional[str],
        indent: str,
        stock_root: Optional[str] = None,
        stock_alias: Optional[str] = None,
    ) -> str:
        inner = indent + "    "
        if alias:
            body = f"{inner}alias {alias};\n"
        elif stock_alias:
            body = f"{inner}alias {stock_alias};\n"
        else:
            assert stock_root is not None
            body = f"{inner}root {stock_root};\n"
        return (
            f"{indent}location = {uri} {{\n"
            f"{inner}internal;\n"
            f"{inner}default_type text/html;\n"
            f"{body}"
            f"{indent}}}\n"
        )
