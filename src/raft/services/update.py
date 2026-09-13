"""Re-install the raft CLI from GitHub (`raft update`)."""

from __future__ import annotations

import os
from typing import Optional

from ..adapters.shell import Shell
from ..models import Stack
from ..ui import say

DEFAULT_INSTALL_URL = "https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh"


class SelfUpdate:
    def __init__(self, stack: Stack, shell: Optional[Shell] = None) -> None:
        self.stack = stack
        self.sh = shell or Shell(stack.root)

    def run(self) -> None:
        url = os.environ.get("RAFT_INSTALL_URL", DEFAULT_INSTALL_URL)
        say("Updating raft…", style="info")
        self.sh.run(
            [
                "bash",
                "-c",
                'export RAFT_INSTALL_QUIET=1; curl -fsSL "$1" | bash',
                "_",
                url,
            ],
        )
        say("OK: raft updated", style="ok")
