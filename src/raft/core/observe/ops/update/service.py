"""Re-install the raft CLI from GitHub (`raft update`)."""

import os
from typing import Optional, TextIO

from raft.core.platform.adapters.shell import Shell
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.core.ui import OperatorSay
from raft.core.core.ui.progress import TerminalProgress
from .identity import InstallIdentity

DEFAULT_INSTALL_URL = "https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh"


class SelfUpdate:
    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.sh = Shell(stack.root)
        self._identity = InstallIdentity()

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
        before = self._identity.read()
        self._set_label("updating")
        self._run_installer(url)
        self._set_label("verifying")
        after = self._identity.read()
        TerminalProgress.finish_active()
        self._finish(before, after)

    def _finish(self, before: Optional[str], after: Optional[str]) -> None:
        if not self._already_current(before, after):
            GraphEventStore(self.stack.root).record_update()
        self._announce(before, after)

    @staticmethod
    def _already_current(before: Optional[str], after: Optional[str]) -> bool:
        return before is not None and before == after

    @staticmethod
    def _set_label(label: str) -> None:
        active = TerminalProgress.active()
        if active is not None:
            active.set_text(label)

    @staticmethod
    def _announce(before: Optional[str], after: Optional[str]) -> None:
        if SelfUpdate._already_current(before, after):
            OperatorSay.say("raft is already up to date", style="info")
            return
        OperatorSay.say("OK: raft updated", style="ok")
        OperatorSay.say(
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
