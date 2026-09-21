"""Doctor facade — compose check suites + report writer."""

from __future__ import annotations

from typing import Optional, Sequence, TextIO

from ...adapters import DockerStack, Shell
from ...models import Stack
from ..auth import GitAuthManager
from .checks import CHECK_SUITES, auth_deploy_key_fix
from .checks.base import CheckSuite
from .context import DoctorContext
from .models import CheckResult
from .report import GroupReportWriter


class Doctor:
    """Environment diagnostics for operators (`raft doctor`)."""

    def __init__(
        self,
        stack: Stack,
        *,
        shell: Optional[Shell] = None,
        auth: Optional[GitAuthManager] = None,
        docker: Optional[DockerStack] = None,
        suites: Optional[Sequence[CheckSuite]] = None,
        reporter: Optional[GroupReportWriter] = None,
    ) -> None:
        self.stack = stack
        self.sh = shell or Shell(stack.root)
        self.auth = auth or GitAuthManager(stack, self.sh)
        self.docker = docker or DockerStack(stack, self.sh)
        self._ctx = DoctorContext(
            stack=self.stack,
            shell=self.sh,
            auth=self.auth,
            docker=self.docker,
        )
        self._suites: tuple[CheckSuite, ...] = tuple(suites) if suites is not None else CHECK_SUITES
        self._reporter = reporter or GroupReportWriter()

    def run(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        for suite in self._suites:
            results.extend(suite.run(self._ctx))
        return results

    def report(
        self,
        results: Optional[list[CheckResult]] = None,
        *,
        out: Optional[TextIO] = None,
        color: Optional[bool] = None,
    ) -> int:
        resolved = results if results is not None else self.run()
        return self._reporter.write(self.stack, resolved, out=out, color=color)

    @staticmethod
    def _auth_deploy_key_fix(service: str, repo_url: str) -> str:
        """Compat shim for unit tests; prefer ``auth_deploy_key_fix``."""
        return auth_deploy_key_fix(service, repo_url)
