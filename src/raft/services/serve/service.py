"""Blocking localhost HTTP server for ``raft serve``."""

from __future__ import annotations

from typing import Optional

import uvicorn

from ...models import Stack
from ..ops.status import Status
from .app import ServeAppFactory
from .instructions import ServeInstructions

DEFAULT_SERVE_PORT = 8787
_BIND_HOST = "127.0.0.1"


class Serve:
    """Operator-invoked localhost UI (foreground; Ctrl+C stops)."""

    def __init__(self, stack: Stack, status: Optional[Status] = None) -> None:
        self.stack = stack
        self._status = status

    def run(self, port: int = DEFAULT_SERVE_PORT) -> None:
        """Print tunnel CTAs, then block on uvicorn until SIGINT."""
        ServeInstructions(port).print()
        app = ServeAppFactory(self.stack, status=self._status).create()
        uvicorn.run(app, host=_BIND_HOST, port=port, log_level="warning")
