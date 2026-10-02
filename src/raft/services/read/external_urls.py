"""Derive public absolute URLs for serve status rows from App + edge config."""

from __future__ import annotations

from typing import Optional, Tuple

from ...config.settings_types import EdgeConfig
from ...models import App, Stack
from ...models.manifest import AppSpec


class ExternalUrlBuilder:
    """Map Compose service ids to operator-facing ``https://…`` / ``http://…`` links."""

    def __init__(self, stack: Stack, edge: EdgeConfig) -> None:
        self._stack = stack
        self._edge = edge
        self._by_compose = {app.compose_id: app for app in stack.apps}

    def urls_for(self, *, service: str, role: str) -> Tuple[str, ...]:
        if role != "app":
            return ()
        app = self._by_compose.get(service)
        if app is None or not app.public_host.strip():
            return ()
        return self._urls_for_app(app)

    def _urls_for_app(self, app: App) -> Tuple[str, ...]:
        spec = self._stack.spec_for(app)
        if not spec.http_ports():
            return ()
        scheme_port = self._scheme_and_port(spec)
        if scheme_port is None:
            return ()
        scheme, port = scheme_port
        return tuple(
            self._format_url(scheme, host, port) for host in spec.server_names(app.public_host)
        )

    def _scheme_and_port(self, spec: AppSpec) -> Optional[Tuple[str, int]]:
        """Prefer HTTPS for ``tls: origin``; else HTTP; HTTPS-only edge as fallback."""
        if spec.tls == "origin" and self._edge.https is not None:
            return ("https", self._edge.https)
        if self._edge.http is not None:
            return ("http", self._edge.http)
        if self._edge.https is not None:
            return ("https", self._edge.https)
        return None

    @staticmethod
    def _format_url(scheme: str, host: str, port: int) -> str:
        default = 443 if scheme == "https" else 80
        if port == default:
            return f"{scheme}://{host}/"
        return f"{scheme}://{host}:{port}/"
