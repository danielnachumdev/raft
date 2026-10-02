"""Doctor facade — compose check suites + report writer."""

from __future__ import annotations

from typing import Optional, TextIO

from ....adapters import DockerStack, Shell
from ....models import Stack
from ...auth import GitAuthManager
from .checks import CHECK_SUITES
from .context import DoctorContext
from .models import CheckResult
from .progress import DoctorProgress
from .report import GroupReportWriter


class Doctor:
    """Environment diagnostics for operators (`raft doctor`)."""

    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.sh = Shell(stack.root)
        self.auth = GitAuthManager(stack)
        self.docker = DockerStack(stack, self.sh)
        self._suites = CHECK_SUITES
        self._reporter = GroupReportWriter()

    def run(self, *, progress: Optional[DoctorProgress] = None) -> list[CheckResult]:
        ctx = self._context(progress)
        results: list[CheckResult] = []
        for suite in self._suites:
            ctx.progress(suite.name)
            results.extend(suite.run(ctx))
        return results

    def report(
        self,
        results: Optional[list[CheckResult]] = None,
        *,
        out: Optional[TextIO] = None,
        color: Optional[bool] = None,
        progress_stream: Optional[TextIO] = None,
    ) -> int:
        resolved = results if results is not None else self._run_with_progress(progress_stream)
        return self._reporter.write(self.stack, resolved, out=out, color=color)

    def _run_with_progress(self, stream: Optional[TextIO]) -> list[CheckResult]:
        with DoctorProgress(stream) as progress:
            return self.run(progress=progress)

    def _context(self, progress: Optional[DoctorProgress]) -> DoctorContext:
        on_progress = progress.update if progress is not None else None
        return DoctorContext(
            stack=self.stack,
            shell=self.sh,
            auth=self.auth,
            docker=self.docker,
            on_progress=on_progress,
        )
