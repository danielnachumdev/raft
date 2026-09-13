"""Re-install the raft CLI from GitHub (`raft update`)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from ..adapters.shell import Shell
from ..models import Stack
from ..ui import say

DEFAULT_INSTALL_URL = "https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh"


def _tool_env_root() -> Optional[Path]:
    """Locate the uv tool environment that provides ``raft`` on PATH, if any."""
    raft_bin = shutil.which("raft")
    if raft_bin:
        resolved = Path(raft_bin).resolve()
        if resolved.parent.name == "bin":
            return resolved.parent.parent
    tool_dir = os.environ.get("UV_TOOL_DIR")
    root = Path(tool_dir) / "raft" if tool_dir else Path.home() / ".local" / "share" / "uv" / "tools" / "raft"
    return root if root.is_dir() else None


def install_identity() -> Optional[str]:
    """Stable identity of the installed raft tool (git commit / dist metadata).

    Prefers ``direct_url.json`` (includes VCS commit for git installs). Falls back
    to ``METADATA``. Returns ``None`` when no install can be inspected.
    """
    tool_root = _tool_env_root()
    if tool_root is None:
        return None
    dist_infos = sorted(tool_root.glob("lib/python*/site-packages/raft-*.dist-info"))
    if not dist_infos:
        return None
    dist_info = dist_infos[0]
    direct_url = dist_info / "direct_url.json"
    if direct_url.is_file():
        return direct_url.read_text(encoding="utf-8").strip()
    metadata = dist_info / "METADATA"
    if metadata.is_file():
        return metadata.read_text(encoding="utf-8").strip()
    return None


class SelfUpdate:
    def __init__(self, stack: Stack, shell: Optional[Shell] = None) -> None:
        self.stack = stack
        self.sh = shell or Shell(stack.root)

    def run(self) -> None:
        url = os.environ.get("RAFT_INSTALL_URL", DEFAULT_INSTALL_URL)
        before = install_identity()
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
        after = install_identity()
        if before is not None and before == after:
            say("raft is already up to date", style="info")
            return
        say("OK: raft updated", style="ok")
