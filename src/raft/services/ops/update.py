"""Re-install the raft CLI from GitHub (`raft update`)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional, TextIO

from raft.errors import OperatorError

from ...adapters.shell import Shell
from ...models import Stack
from ...ui import say
from ...ui.progress import TerminalProgress

DEFAULT_INSTALL_URL = "https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh"


def _tool_env_root() -> Optional[Path]:
    """Locate the uv tool environment that provides ``raft`` on PATH, if any."""
    raft_bin = shutil.which("raft")
    if raft_bin:
        resolved = Path(raft_bin).resolve()
        if resolved.parent.name == "bin":
            return resolved.parent.parent
    tool_dir = os.environ.get("UV_TOOL_DIR")
    root = (
        Path(tool_dir) / "raft"
        if tool_dir
        else Path.home() / ".local" / "share" / "uv" / "tools" / "raft"
    )
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
    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.sh = Shell(stack.root)

    def run(self, *, progress_stream: Optional[TextIO] = None) -> None:
        url = os.environ.get("RAFT_INSTALL_URL", DEFAULT_INSTALL_URL)
        self._run_with_progress(url, progress_stream)

    def _run_with_progress(self, url: str, stream: Optional[TextIO]) -> None:
        existing = TerminalProgress.active()
        if existing is not None:
            self._run_body(url)
            return
        with TerminalProgress(stream, prefix="raft update", label="updating"):
            self._run_body(url)

    def _run_body(self, url: str) -> None:
        self._set_label("checking install")
        before = install_identity()
        self._set_label("updating")
        self._run_installer(url)
        self._set_label("verifying")
        after = install_identity()
        TerminalProgress.finish_active()
        self._announce(before, after)

    @staticmethod
    def _set_label(label: str) -> None:
        active = TerminalProgress.active()
        if active is not None:
            active.set_text(label)

    @staticmethod
    def _announce(before: Optional[str], after: Optional[str]) -> None:
        if before is not None and before == after:
            say("raft is already up to date", style="info")
            return
        say("OK: raft updated", style="ok")
        say(
            "Next: align the running stack with this release — templates and "
            "Compose ids can change. Typical path: `raft render`, then "
            "`raft redeploy <app|router>` for targeted updates, or "
            "`raft down && raft up` when edge/service names or schemas shifted. "
            "Finish with `raft doctor`.",
            style="info",
        )

    def _run_installer(self, url: str) -> None:
        try:
            self.sh.run(
                [
                    "bash",
                    "-c",
                    'export RAFT_INSTALL_QUIET=1; curl -fsSL "$1" | bash',
                    "_",
                    url,
                ],
            )
        except Exception as exc:
            TerminalProgress.finish_active()
            raise OperatorError(
                "raft update failed (could not download/run the installer).\n"
                f"Fix: check outbound HTTPS, then retry `raft update`\n"
                f"     or run manually: curl -fsSL {url} | bash"
            ) from exc
