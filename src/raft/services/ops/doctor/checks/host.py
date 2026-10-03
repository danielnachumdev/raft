"""Host/platform checks: compose templates, generated files, docker daemon."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from ..context import DoctorContext
from ..models import INFRA, CheckResult

_METRICS_REL = Path("state") / "metrics" / "resources.jsonl"
_METRICS_CHOWN = (
    'sudo chown "$(whoami):$(whoami)" '
    '"${RAFT_DATA_HOME:-$HOME/.raft}/state/metrics" '
    '"${RAFT_DATA_HOME:-$HOME/.raft}/state/metrics/resources.jsonl"'
)


class HostChecks:
    name = "host"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        out: list[CheckResult] = [
            self._compose_file(ctx),
            self._generated(ctx),
        ]
        out.extend(self._docker(ctx))
        out.extend(self._metrics_if_bad(ctx))
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

    def _metrics_if_bad(self, ctx: DoctorContext) -> list[CheckResult]:
        result = self._metrics(ctx)
        return [] if result is None else [result]

    def _metrics(self, ctx: DoctorContext) -> Optional[CheckResult]:
        path = ctx.stack.root / _METRICS_REL
        parent = path.parent
        if not parent.is_dir():
            return None
        if not os.access(parent, os.W_OK):
            return self._metrics_fail(parent)
        if path.is_file() and not os.access(path, os.W_OK):
            return self._metrics_fail(path)
        return None

    @staticmethod
    def _metrics_fail(path: Path) -> CheckResult:
        return CheckResult(
            INFRA,
            "metrics",
            "fail",
            f"not writable by host user: {path}",
            fix=_METRICS_CHOWN,
        )
