"""Blocking localhost HTTP server for ``raft serve``."""

from __future__ import annotations

from typing import Optional

import uvicorn

from ...models import Stack
from ...ui import say
from ..ops.status import Status
from .app import ServeAppFactory
from .instructions import ServeInstructions
from .runtime import ServeRuntime

DEFAULT_SERVE_PORT = 8787
_BIND_HOST = "127.0.0.1"


class Serve:
    """Operator-invoked localhost UI (foreground; Ctrl+C or ``--stop``)."""

    def __init__(self, stack: Stack, status: Optional[Status] = None) -> None:
        self.stack = stack
        self._status = status
        self._runtime = ServeRuntime(stack.root)

    def run(self, port: int = DEFAULT_SERVE_PORT) -> None:
        """Print tunnel CTAs, then block on uvicorn until SIGINT."""
        lease = self._runtime.acquire(port)
        try:
            ServeInstructions(port).print()
            app = ServeAppFactory(self.stack, status=self._status).create()
            uvicorn.run(app, host=_BIND_HOST, port=port, log_level="warning")
        finally:
            lease.release()

    def stop(self, port: int = DEFAULT_SERVE_PORT) -> None:
        """Stop a serve process on ``port`` in another process (no-op if idle)."""
        if self._runtime.stop(port):
            say(f"stopped raft serve on 127.0.0.1:{port}", style="ok")
            return
        say(f"raft serve is not running on 127.0.0.1:{port}", style="info")
