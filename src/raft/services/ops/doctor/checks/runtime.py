"""Compose runtime: which core services are up."""

from __future__ import annotations

import shutil

from ..context import DoctorContext
from ..models import INFRA, CheckResult


class RuntimeChecks:
    name = "runtime"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        if not shutil.which("docker"):
            return [CheckResult(INFRA, "stack", "warn", "skipped (docker unavailable)")]
        try:
            running = set(ctx.docker.running_services())
        except Exception as exc:  # noqa: BLE001
            return [
                CheckResult(
                    INFRA,
                    "stack",
                    "warn",
                    f"could not query compose: {exc}",
                    fix="ensure compose.yaml is valid and docker works",
                )
            ]
        return [*self._edge_running(ctx, running), self._stack_summary(ctx, running)]

    @staticmethod
    def _edge_running(ctx: DoctorContext, running: set[str]) -> list[CheckResult]:
        results: list[CheckResult] = []
        for name in (ctx.stack.gate, ctx.stack.router):
            if name in running:
                results.append(CheckResult(name, "running", "ok", "up"))
            else:
                results.append(CheckResult(name, "running", "warn", "not running", fix="raft up"))
        return results

    @staticmethod
    def _stack_summary(ctx: DoctorContext, running: set[str]) -> CheckResult:
        expected = list(ctx.stack.core_services)
        missing = [s for s in expected if s not in running]
        if not missing:
            return CheckResult(INFRA, "stack", "ok", f"running: {', '.join(expected)}")
        if not running:
            return CheckResult(INFRA, "stack", "warn", "no core services running", fix="raft up")
        return CheckResult(
            INFRA,
            "stack",
            "warn",
            f"running {sorted(running)}; missing {missing}",
            fix="raft up   # or redeploy the missing service",
        )
