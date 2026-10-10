"""Warn when ``spec.envFile`` is missing or group/world-readable."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from raft.secrets.app_secrets import ENV_FILE_MODE, AppSecretsLayout
from raft.errors.cta import OperatorError
from raft.render.env_file_path import ComposeEnvFilePath

from ..context import DoctorContext
from ..models import CheckResult

_OTHER_BITS = 0o077


class EnvFileChecks:
    """Permission / presence checks for App secret env files (warn-only)."""

    name = "env_file"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        results: list[CheckResult] = []
        for app in ctx.stack.apps:
            result = self._check_app(ctx, app)
            if result is not None:
                results.append(result)
        return results

    def _check_app(self, ctx: DoctorContext, app) -> Optional[CheckResult]:
        env_file = self._env_file(ctx, app)
        if not env_file:
            return None
        path = Path(ComposeEnvFilePath(ctx.stack.root).for_runtime(env_file))
        recommended = AppSecretsLayout(ctx.stack.root).env_file(app.name)
        if not path.is_file():
            return self._missing(app, path, recommended)
        loose = self._loose_path(path) or self._loose_path(path.parent)
        if loose is not None:
            return self._permissive(app, loose)
        mode = f"{path.stat().st_mode & 0o777:04o}"
        return CheckResult(
            app.compose_id,
            "env_file",
            "ok",
            f"mode {mode} {path}",
        )

    @staticmethod
    def _env_file(ctx: DoctorContext, app) -> Optional[str]:
        try:
            return ctx.stack.spec_for(app).env_file
        except (OSError, ValueError, FileNotFoundError, OperatorError):
            return None

    def _missing(self, app, path: Path, recommended: Path) -> CheckResult:
        return CheckResult(
            app.compose_id,
            "env_file",
            "warn",
            f"envFile missing: {path}",
            fix=(
                f"create {recommended} (mode {ENV_FILE_MODE:04o}), "
                f"point spec.envFile at it, then re-apply"
            ),
        )

    def _permissive(self, app, path: Path) -> CheckResult:
        mode = f"{path.stat().st_mode & 0o777:04o}"
        return CheckResult(
            app.compose_id,
            "env_file",
            "warn",
            f"envFile path is group/world-readable ({mode}): {path}",
            fix=(
                f"chmod {ENV_FILE_MODE:04o} on the env file and "
                f"chmod 0700 on its directory (see docs/secrets.md)"
            ),
        )

    @staticmethod
    def _loose_path(path: Path) -> Optional[Path]:
        try:
            mode = path.stat().st_mode
        except OSError:
            return None
        if mode & _OTHER_BITS:
            return path
        return None
