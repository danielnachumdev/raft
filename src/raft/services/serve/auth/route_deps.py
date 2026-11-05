"""Attach read/write RBAC Depends lists to FastAPI routes."""

from typing import Callable

from fastapi import Depends

from raft.services.serve.auth.require import require_read, require_write


class RouteRbacDeps:
    """``RouteRbacDeps(\"firewall\").read`` / ``.write`` for ``dependencies=[…]``."""

    def __init__(self, resource: str) -> None:
        self.read = [Depends(require_read(resource))]
        self.write = [Depends(require_write(resource))]

    def get(self, app, path: str, handler: Callable) -> None:
        app.get(path, dependencies=self.read)(handler)

    def mut(self, app, method: str, path: str, handler: Callable) -> None:
        getattr(app, method)(path, dependencies=self.write)(handler)
