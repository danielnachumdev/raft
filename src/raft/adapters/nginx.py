"""Nginx upstream file management (keyed by app + port name)."""

from __future__ import annotations

import logging
from typing import Optional

from raft.errors import OperatorError

from ..models.app import App
from ..models.ports import PortSpec
from ..models.stack import Stack
from .docker import DockerStack

logger = logging.getLogger(__name__)


class NginxUpstreamText:
    """Canonical ``upstream { … }`` snippet body (render + live cutover)."""

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


class NginxUpstreams:
    def __init__(self, stack: Stack, docker: DockerStack) -> None:
        self.stack = stack
        self.docker = docker

    def _http_ports(self, app: App) -> tuple[PortSpec, ...]:
        try:
            return self.stack.spec_for(app).http_ports()
        except (FileNotFoundError, OperatorError):
            return (PortSpec(name="http", container_port=80, expose="http"),)

    def ensure_steady_file(self, app: App) -> None:
        for port in self._http_ports(app):
            path = self.stack.upstream_file(app, port)
            if path.is_file():
                logger.debug("upstream file already exists for %s/%s", app.name, port.name)
                continue
            self.point_at(app, app.compose_id, port=port, reload=False)

    def point_at(
        self,
        app: App,
        target_hostname: str,
        *,
        port: Optional[PortSpec] = None,
        reload: bool = True,
    ) -> None:
        ports = (port,) if port is not None else self._http_ports(app)
        for p in ports:
            self._write_upstream(app, target_hostname, p)
            if reload:
                self._assert_router_sees(app, target_hostname, p)

    def _write_upstream(self, app: App, target_hostname: str, p: PortSpec) -> None:
        path = self.stack.upstream_file(app, p)
        upstream = self.stack.upstream_name(app, p)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            NginxUpstreamText.block(upstream, target_hostname, p.container_port),
            encoding="utf-8",
        )
        logger.info(
            "point %s/%s upstream at %s:%s",
            app.name,
            p.name,
            target_hostname,
            p.container_port,
        )

    def _assert_router_sees(self, app: App, target_hostname: str, p: PortSpec) -> None:
        if self.docker.router_sees_upstream_target(app, target_hostname, p):
            return
        raise OperatorError(
            f"router container does not see upstream target {target_hostname!r} yet.\n"
            f"Fix: wait for the router mount sync, or: raft redeploy router; "
            f"verify generated/nginx/upstreams/"
        )
