"""Nginx upstream file management (keyed by app + port name)."""

from __future__ import annotations

import logging
from typing import Optional

from ..models.app import App
from ..models.ports import PortSpec
from ..models.stack import Stack
from .docker import DockerStack

logger = logging.getLogger(__name__)


class NginxUpstreams:
    def __init__(self, stack: Stack, docker: DockerStack) -> None:
        self.stack = stack
        self.docker = docker

    def _http_ports(self, app: App) -> tuple[PortSpec, ...]:
        try:
            return self.stack.spec_for(app).http_ports()
        except FileNotFoundError:
            return (PortSpec(name="http", container_port=80, expose="http"),)

    def ensure_steady_file(self, app: App) -> None:
        for port in self._http_ports(app):
            path = self.stack.upstream_file(app, port)
            if path.is_file():
                logger.debug("upstream file already exists for %s/%s", app.name, port.name)
                continue
            self.point_at(app, app.name, port=port, reload=False)

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
            path = self.stack.upstream_file(app, p)
            upstream = self.stack.upstream_name(app, p)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "# Managed by raft — do not hand-edit while deploying.\n"
                f"upstream {upstream} {{\n"
                f"    server {target_hostname}:{p.container_port};\n"
                "}\n",
                encoding="utf-8",
            )
            logger.info(
                "point %s/%s upstream at %s:%s",
                app.name,
                p.name,
                target_hostname,
                p.container_port,
            )
            if not reload:
                continue
            if not self.docker.router_sees_upstream_target(app, target_hostname, p):
                raise RuntimeError(
                    f"router container does not see upstream target {target_hostname!r} yet"
                )
