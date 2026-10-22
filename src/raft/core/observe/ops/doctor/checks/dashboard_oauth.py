"""Warn when dashboard oauth is enabled but secrets/allowlist are missing."""

from __future__ import annotations

from raft.core.core.config.settings import SettingsLoader
from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.lifecycle.dashboard.oauth_env import REQUIRED_OAUTH_ENV
from raft.core.lifecycle.dashboard.oauth_ops import DashboardOAuthOps

from ..context import DoctorContext
from ..models import INFRA, CheckResult


class DashboardOauthChecks:
    """OAuth readiness for enabled ``raft-dashboard`` (warn-only)."""

    name = "dashboard_oauth"

    def run(self, ctx: DoctorContext) -> list[CheckResult]:
        cfg = SettingsLoader().load(ctx.stack.root).dashboard
        if not cfg.enabled or cfg.auth.mode != "oauth":
            return []
        return [self._result(ctx, cfg)]

    def _result(self, ctx: DoctorContext, cfg: DashboardConfig) -> CheckResult:
        if DashboardOAuthOps(ctx.stack.root).secrets_ready(cfg):
            return CheckResult(
                INFRA,
                "dashboard_oauth",
                "ok",
                "oauth.env and allowlist present",
            )
        keys = ", ".join(REQUIRED_OAUTH_ENV)
        return CheckResult(
            INFRA,
            "dashboard_oauth",
            "warn",
            "dashboard oauth secrets or allowlist missing",
            fix=(
                f"write host/secrets/dashboard/oauth.env ({keys}) and "
                f"the allowlist file, then raft render && "
                f"raft redeploy dashboard"
            ),
        )
