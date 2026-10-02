"""Stdout connection instructions for terminal-only VMs."""

from __future__ import annotations

import sys
from typing import Optional, TextIO


class ServeInstructions:
    """Print VM URL + SSH / gcloud port-forward examples before listening."""

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
            "This VM is terminal-only — open the UI from your laptop via a tunnel:\n"
            "\n"
            f"  ssh -L {port}:127.0.0.1:{port} USER@VM_HOST\n"
            f"  gcloud compute ssh VM_NAME --zone=ZONE -- -L {port}:127.0.0.1:{port}\n"
            "\n"
            f"Then open {url} in your laptop browser.\n"
            "Stop with Ctrl+C.\n"
            "\n"
        )
