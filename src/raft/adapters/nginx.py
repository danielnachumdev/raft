"""Nginx upstream file management."""

import logging

from .docker import DockerStack
from ..models.inventory import App, Stack

logger = logging.getLogger(__name__)

class NginxUpstreams:
    def __init__(self, stack: Stack, docker: DockerStack) -> None:
        self.stack = stack
        self.docker = docker

    def _port(self, app: App) -> int:
        try:
            return self.stack.contract_for(app).port
        except FileNotFoundError:
            return 80

    def ensure_steady_file(self, app: App) -> None:
        path = self.stack.upstream_file(app)
        if path.is_file():
            logger.debug("upstream file already exists for %s", app.name)
            return
        self.point_at(app, app.name, reload=False)

    def point_at(self, app: App, target_hostname: str, *, reload: bool = True) -> None:
        path = self.stack.upstream_file(app)
        port = self._port(app)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "# Managed by raft — do not hand-edit while deploying.\n"
            f"upstream {app.name}_upstream {{\n"
            f"    server {target_hostname}:{port};\n"
            "}\n",
            encoding="utf-8",
        )
        logger.info("point %s upstream at %s:%s", app.name, target_hostname, port)
        if not reload:
            return
        if not self.docker.router_sees_upstream_target(app, target_hostname):
            raise RuntimeError(
                f"router container does not see upstream target {target_hostname!r} yet"
            )
