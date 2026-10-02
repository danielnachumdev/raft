"""Doctor facade — compose check suites + report writer."""

from __future__ import annotations

from typing import Optional, TextIO

from ....adapters import DockerStack, Shell
from ....models import Stack
from ...auth import GitAuthManager
from .checks import CHECK_SUITES
from .checks.base import CheckSuite
from .context import DoctorContext
from .models import CheckResult
from .observability import ComposeCallCounter, SuiteTiming
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
        counter = ComposeCallCounter()
        counter.install(self.sh, getattr(self.docker, "sh", None))
        try:
            return self._run_suites(progress, counter)
        finally:
            counter.uninstall()

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

    def _run_suites(
        self,
        progress: Optional[DoctorProgress],
        counter: ComposeCallCounter,
    ) -> list[CheckResult]:
        ctx = self._context(progress)
        results: list[CheckResult] = []
        for suite in self._suites:
            results.extend(self._run_suite(suite, ctx))
        counter.log_summary()
        return results

    def _run_suite(self, suite: CheckSuite, ctx: DoctorContext) -> list[CheckResult]:
        timing = SuiteTiming(suite.name)
        timing.start()
        ctx.progress(suite.name)
        try:
            return suite.run(ctx)
        finally:
            timing.done()

    def _context(self, progress: Optional[DoctorProgress]) -> DoctorContext:
        on_progress = progress.update if progress is not None else None
        return DoctorContext(
            stack=self.stack,
            shell=self.sh,
            auth=self.auth,
            docker=self.docker,
            on_progress=on_progress,
        )
