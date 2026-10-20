"""Re-install the raft CLI from GitHub (`raft update`)."""

import os
from typing import Optional, TextIO

from raft.core.platform.adapters.shell import Shell
from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.stack import Stack
from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.core.ui.progress import TerminalProgress
from raft.core.observe.ops.version import InstalledVersion
from .announce import UpdateAnnounce
from .host_apply import HostApplyGate
from .host_docker import HostDockerUpdate
from .identity import InstallIdentity
from .install_cmd import DEFAULT_INSTALL_URL, InstallCmd
from .outcome import UpdateOutcome


class SelfUpdate:
    def __init__(
        self,
        stack: Stack,
        *,
        host_gate: Optional[HostApplyGate] = None,
    ) -> None:
        self.stack = stack
        self.sh = Shell(stack.root)
        self._identity = InstallIdentity()
        self._versions = InstalledVersion()
        self._announce = UpdateAnnounce()
        self._host_gate = host_gate or HostApplyGate()

    def run(
        self,
        *,
        ref: Optional[str] = None,
        progress_stream: Optional[TextIO] = None,
        announce: bool = True,
    ) -> UpdateOutcome:
        self._host_gate.ensure()
        url = os.environ.get("RAFT_INSTALL_URL", DEFAULT_INSTALL_URL)
        return self._run_with_progress(url, ref, progress_stream, announce)

    def _run_with_progress(
        self,
        url: str,
        ref: Optional[str],
        stream: Optional[TextIO],
        announce: bool,
    ) -> UpdateOutcome:
        existing = TerminalProgress.active()
        if existing is not None:
            return self._run_body(url, ref, announce)
        with TerminalProgress(stream, prefix="raft update", label="updating"):
            return self._run_body(url, ref, announce)

    def _run_body(
        self, url: str, ref: Optional[str], announce: bool
    ) -> UpdateOutcome:
        self._set_label("checking install")
        before_id = self._identity.read()
        before_line = self._version_line()
        self._set_label("updating")
        self._run_installer(url, ref)
        self._set_label("verifying")
        after_id = self._identity.read()
        after_line = self._version_line()
        self._reject_empty_host_identity(after_id)
        TerminalProgress.finish_active()
        return self._finish(before_id, after_id, before_line, after_line, announce)

    def _finish(
        self,
        before_id: Optional[str],
        after_id: Optional[str],
        before_line: Optional[str],
        after_line: Optional[str],
        announce: bool,
    ) -> UpdateOutcome:
        current = self._already_current(before_id, after_id)
        if not current:
            GraphEventStore(self.stack.root).record_update()
        outcome = UpdateOutcome(
            already_current=current,
            before_line=before_line,
            after_line=after_line,
        )
        if announce:
            self._announce.say_outcome(outcome)
        return outcome

    def _version_line(self) -> Optional[str]:
        dist = self._identity.dist_info_dir()
        if dist is None:
            return None
        return self._versions.line_for_dist_info(dist)

    def _reject_empty_host_identity(self, after_id: Optional[str]) -> None:
        if after_id is not None or not self._host_gate.uses_host_docker():
            return
        home = (os.environ.get("RAFT_HOST_HOME") or "").strip() or "(unset)"
        TerminalProgress.finish_active()
        raise OperatorError(
            "Host raft update finished but the CLI was not found under "
            f"RAFT_HOST_HOME ({home}).\n"
            "Fix: confirm the host home /.local mount, then retry, "
            "or run `raft update` on the host."
        )

    @staticmethod
    def _already_current(before: Optional[str], after: Optional[str]) -> bool:
        return before is not None and before == after

    @staticmethod
    def _set_label(label: str) -> None:
        active = TerminalProgress.active()
        if active is not None:
            active.set_text(label)

    def _run_installer(self, url: str, ref: Optional[str]) -> None:
        if self._host_gate.uses_host_docker():
            HostDockerUpdate(self.sh).run(url, ref)
            return
        try:
            self.sh.run(InstallCmd.in_process_argv(url, ref))
        except Exception as exc:
            TerminalProgress.finish_active()
            raise OperatorError(
                "raft update failed (could not download/run the installer).\n"
                f"Fix: check outbound HTTPS, then retry `raft update`\n"
                f"     or run manually: curl -fsSL {url} | bash"
            ) from exc
