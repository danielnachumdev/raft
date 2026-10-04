"""Stdout connection instructions for localhost-only serve."""

from __future__ import annotations

import sys
from typing import Optional, TextIO


class ServeInstructions:
    """Print bind URL and a generic port-forward example before listening."""

    def __init__(self, port: int) -> None:
        self.port = port

    def print(self, out: Optional[TextIO] = None) -> None:
        stream = out if out is not None else sys.stdout
        stream.write(self.render())
        stream.flush()

    def render(self) -> str:
        port = self.port
        url = f"http://127.0.0.1:{port}/"
        return (
            f"raft serve listening on {url} (localhost only)\n"
            "\n"
            "Open that URL on the host, or forward the port from elsewhere:\n"
            "\n"
            f"  ssh -L {port}:127.0.0.1:{port} USER@HOST\n"
            "\n"
            f"Then open {url} in a browser.\n"
            "Stop with Ctrl+C, or from another shell: raft serve --stop\n"
            "\n"
        )
