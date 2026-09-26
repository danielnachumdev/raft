"""Host/platform checks: compose templates, generated files, docker daemon."""

from __future__ import annotations

import shutil

from ..context import DoctorContext
from ..models import INFRA, CheckResult


class HostChecks:
    name = "host"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        out: list[CheckResult] = [
            self._compose_file(ctx),
            self._generated(ctx),
        ]
        out.extend(self._docker(ctx))
        return out

    def _compose_file(self, ctx: DoctorContext) -> CheckResult:
        path = ctx.stack.root / "compose.yaml"
        if path.is_file():
            return CheckResult(INFRA, "compose.yaml", "ok", str(path))
        return CheckResult(
            INFRA,
            "compose.yaml",
            "fail",
            f"missing at {path}",
            fix="run `raft render` (syncs Compose templates into ~/.raft)",
        )

    def _generated(self, ctx: DoctorContext) -> CheckResult:
        path = ctx.stack.root / "generated" / "compose.apps.yaml"
        if path.is_file():
            return CheckResult(INFRA, "generated", "ok", str(path))
        return CheckResult(
            INFRA,
            "generated",
            "fail",
            "missing generated/compose.apps.yaml",
            fix="raft sync   # or: raft render",
        )

    def _docker(self, ctx: DoctorContext) -> list[CheckResult]:
        if not shutil.which("docker"):
            return [
                CheckResult(
                    INFRA,
                    "docker",
                    "fail",
                    "docker CLI not found on PATH",
                    fix="install Docker Engine and ensure `docker` is on PATH",
                )
            ]
        probe = ctx.shell.run(["docker", "info"], check=False, capture=True)
        if probe.returncode != 0:
            return [self._docker_daemon_fail(probe)]
        return [CheckResult(INFRA, "docker", "ok", "CLI and daemon reachable")]

    @staticmethod
    def _docker_daemon_fail(probe) -> CheckResult:
        detail = (probe.stderr or probe.stdout or "docker info failed").strip().splitlines()
        brief = detail[-1] if detail else "docker info failed"
        return CheckResult(
            INFRA,
            "docker",
            "fail",
            brief,
            fix="start the Docker daemon (and join the `docker` group if permission denied)",
        )
