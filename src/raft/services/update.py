"""Re-install the raft CLI from GitHub (`raft update`)."""

from __future__ import annotations

import os
from typing import Optional

from ..adapters.shell import Shell
from ..models import Stack
from ..ui import say

# Same raw URL operators use for first-time install (see install.sh / README).
DEFAULT_INSTALL_URL = (
    "https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh"
)


class SelfUpdate:
    """Fetch and re-run ``install.sh`` so the uv tool tracks GitHub (no lasting clone)."""

    def __init__(self, stack: Stack, shell: Optional[Shell] = None) -> None:
        self.stack = stack
        self.sh = shell or Shell(stack.root)

    def run(self) -> None:
        url = os.environ.get("RAFT_INSTALL_URL", DEFAULT_INSTALL_URL)
        say(f"Updating raft from {url}…")
        # Always pipe the remote installer so we get latest install.sh + package
        # from GitHub, and do not leave a durable checkout (see install.sh).
        self.sh.run(
            [
                "bash",
                "-c",
                'curl -fsSL "$1" | bash',
                "_",
                url,
            ],
        )
        say("OK: raft CLI reinstalled (latest from GitHub)")
