"""Doctor suite progress hooks (spinner lives in raft.ui.progress)."""

from __future__ import annotations

import io
from unittest.mock import MagicMock

from raft.ops.doctor import INFRA, CheckResult
from raft.ui.progress import TerminalProgress

from .base import DoctorTestCase


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True


class _NoTty(io.StringIO):
    def isatty(self) -> bool:
        return False


class TestDoctorProgress(DoctorTestCase):
    def test_progress_updates_while_run(self) -> None:
        labels: list[str] = []
        progress = MagicMock()
        progress.update.side_effect = labels.append
        self.seed_compose()
        self.seed_generated_apps()
        docker = self.mock_docker(running=["raft-gate", "raft-router"])
        doctor = self.doctor(shell=self.mock_shell(), docker=docker)
        doctor.run(progress=progress)
        assert labels
        assert "host" in labels
        assert "runtime" in labels

    def test_report_runs_with_progress_hook(self) -> None:
        self.seed_compose()
        self.seed_generated_apps()
        docker = self.mock_docker(running=["raft-gate", "raft-router"])
        doctor = self.doctor(shell=self.mock_shell(), docker=docker)
        out = io.StringIO()
        progress = _NoTty()
        with self.doctor_env():
            doctor.report(out=out, color=False, progress_stream=progress)
        text = out.getvalue()
        assert "raft" in text or "all checks" in text or "check(s)" in text
        assert progress.getvalue() == ""

    def test_precomputed_results_skip_spinner(self) -> None:
        doctor = self.doctor()
        out = io.StringIO()
        progress = _Tty()
        code = doctor.report(
            [CheckResult(INFRA, "docker", "ok", "fine")],
            out=out,
            color=False,
            progress_stream=progress,
        )
        assert code == 0
        assert "all checks passed" in out.getvalue()
        assert progress.getvalue() == ""

    def test_report_reuses_active_spinner(self) -> None:
        self.seed_compose()
        self.seed_generated_apps()
        docker = self.mock_docker(running=["raft-gate", "raft-router"])
        doctor = self.doctor(shell=self.mock_shell(), docker=docker)
        out = io.StringIO()
        labels: list[str] = []
        with TerminalProgress(_NoTty(), prefix="raft doctor", label="checking") as progress:
            progress.update = labels.append  # type: ignore[method-assign]
            with self.doctor_env():
                doctor.report(out=out, color=False)
            assert TerminalProgress.current()._finished
        assert labels
        assert "host" in labels

    def test_context_progress_uses_current_spinner(self) -> None:
        from raft.ops.doctor.context import DoctorContext

        labels: list[str] = []
        with TerminalProgress(_NoTty(), prefix="raft doctor") as progress:
            progress.set_text = labels.append  # type: ignore[method-assign]
            ctx = DoctorContext(
                stack=self.stack,
                shell=self.mock_shell(),
                auth=MagicMock(),
                docker=self.mock_docker(),
                on_progress=None,
            )
            ctx.progress("host")
        assert labels == ["host"]
