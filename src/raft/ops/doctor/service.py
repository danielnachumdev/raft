"""Doctor facade — compose check suites + report writer."""

from __future__ import annotations

from typing import Callable, Optional, TextIO

from raft.adapters import DockerStack, Shell
from raft.models.stack import Stack
from raft.ui.progress import TerminalProgress
from raft.auth import GitAuthManager
from .checks import CHECK_SUITES
from .checks.base import CheckSuite
from .context import DoctorContext
from .models import CheckResult
from .observability import ComposeCallCounter, SuiteTiming
from .report import GroupReportWriter


class Doctor:
    """Environment diagnostics for operators (`raft doctor` / `raft doctor NAME`)."""

    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self.sh = Shell(stack.root)
        self.auth = GitAuthManager(stack)
        self.docker = DockerStack(stack, self.sh)
        self._suites = CHECK_SUITES
        self._reporter = GroupReportWriter()

    def run(
        self,
        *,
        progress: Optional[TerminalProgress] = None,
        app_name: Optional[str] = None,
    ) -> list[CheckResult]:
        counter = ComposeCallCounter()
        counter.install(self.sh, getattr(self.docker, "sh", None))
        try:
            results = self._run_suites(progress, counter)
            return self._filter_results(results, app_name)
        finally:
            counter.uninstall()

    def report(
        self,
        results: Optional[list[CheckResult]] = None,
        *,
        out: Optional[TextIO] = None,
        color: Optional[bool] = None,
        progress_stream: Optional[TextIO] = None,
        app_name: Optional[str] = None,
    ) -> int:
        resolved = (
            results
            if results is not None
            else self._run_with_progress(progress_stream, app_name=app_name)
        )
        TerminalProgress.finish_active()
        return self._reporter.write(self.stack, resolved, out=out, color=color)

    def _run_with_progress(
        self,
        stream: Optional[TextIO],
        *,
        app_name: Optional[str],
    ) -> list[CheckResult]:
        existing = TerminalProgress.active()
        if existing is not None:
            return self.run(progress=existing, app_name=app_name)
        with TerminalProgress(stream, prefix="raft doctor", label="checking") as progress:
            return self.run(progress=progress, app_name=app_name)

    def _run_suites(
        self,
        progress: Optional[TerminalProgress],
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

    def _filter_results(
        self,
        results: list[CheckResult],
        app_name: Optional[str],
    ) -> list[CheckResult]:
        if not app_name:
            return results
        app = self._resolve_filter_app(app_name)
        return [r for r in results if r.service == app.compose_id]

    def _resolve_filter_app(self, app_name: str):
        return self.stack.app(app_name.strip())

    def _context(self, progress: Optional[TerminalProgress]) -> DoctorContext:
        on_progress = self._progress_hook(progress)
        return DoctorContext(
            stack=self.stack,
            shell=self.sh,
            auth=self.auth,
            docker=self.docker,
            on_progress=on_progress,
        )

    @staticmethod
    def _progress_hook(
        progress: Optional[TerminalProgress],
    ) -> Optional[Callable[[str], None]]:
        if progress is not None:
            return progress.update
        active = TerminalProgress.active()
        return active.update if active is not None else None
