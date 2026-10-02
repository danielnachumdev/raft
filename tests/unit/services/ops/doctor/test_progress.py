"""Doctor progress spinner and suite progress hooks."""

from __future__ import annotations

import io
import time
from unittest.mock import MagicMock

from raft.services.ops.doctor import INFRA, CheckResult
from raft.services.ops.doctor.progress import DoctorProgress

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

    def test_spinner_noop_when_not_tty(self) -> None:
        stream = _NoTty()
        with DoctorProgress(stream) as progress:
            progress.update("host")
        assert stream.getvalue() == ""

    def test_spinner_writes_and_clears_on_tty(self) -> None:
        stream = _Tty()
        with DoctorProgress(stream) as progress:
            progress.update("")
            time.sleep(0.2)
        text = stream.getvalue()
        assert "raft doctor:" in text
        assert "\033[K" in text

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
