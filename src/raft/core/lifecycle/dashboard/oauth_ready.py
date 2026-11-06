"""OAuth secret/allowlist readiness without depending on settings writer."""

from pathlib import Path
from typing import Any, Dict, Optional

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.errors.cta import OperatorError

from .oauth_allowlist import DashboardOAuthAllowlist
from .oauth_env import DashboardOAuthEnv


class DashboardOAuthReady:
    """Check oauth.env + allowlist presence for dashboard auth.mode=oauth."""

    def __init__(self, data_home: Path) -> None:
        self._env = DashboardOAuthEnv(data_home)
        self._allow = DashboardOAuthAllowlist(data_home)

    def status_public(self, cfg: DashboardConfig) -> Dict[str, Any]:
        rel = cfg.auth.oauth.allowlist_file
        return {
            "provider": cfg.auth.oauth.provider,
            "issuerUrl": cfg.auth.oauth.issuer_url,
            "redirectPath": cfg.auth.oauth.redirect_path,
            "hasEnvFile": self._env.path().is_file(),
            "hasAllowlist": bool(self._allow.read(rel)),
            "secretsReady": self.secrets_ready(cfg),
        }

    def secrets_ready(self, cfg: DashboardConfig) -> bool:
        return self._env.secrets_present() and self._allow.exists(
            cfg.auth.oauth.allowlist_file
        )

    def require_ready(self, cfg: DashboardConfig) -> None:
        if self.secrets_ready(cfg):
            return
        raise OperatorError(
            "dashboard oauth requires host/secrets/dashboard/oauth.env "
            "and RBAC bindings (allowlist is derived from rbac.yaml).\n"
            "Fix: write oauth.env with OAUTH2_PROXY_CLIENT_ID, "
            "OAUTH2_PROXY_CLIENT_SECRET, OAUTH2_PROXY_COOKIE_SECRET, "
            "OAUTH2_PROXY_REDIRECT_URL; bind subjects in host/rbac.yaml; "
            "set auth.mode: oauth in Settings; then raft render "
            "and redeploy dashboard",
            has_fix=False,
        )
