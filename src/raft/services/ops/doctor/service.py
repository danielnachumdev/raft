"""Doctor facade — compose check suites + report writer."""

from __future__ import annotations

from typing import Optional, TextIO

from ....adapters import DockerStack, Shell
from ....models import Stack
from ...auth import GitAuthManager
from .checks import CHECK_SUITES, auth_deploy_key_fix
from .context import DoctorContext
from .models import CheckResult
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

    def run(self) -> list[CheckResult]:
        ctx = DoctorContext(
            stack=self.stack,
            shell=self.sh,
            auth=self.auth,
            docker=self.docker,
        )
        results: list[CheckResult] = []
        for suite in self._suites:
            results.extend(suite.run(ctx))
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
