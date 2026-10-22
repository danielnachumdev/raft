"""Operator helpers for dashboard OAuth secrets (env + allowlist)."""

from pathlib import Path
from typing import Any, Dict, Optional

from raft.core.core.config.settings.dashboard_config import (
    DASHBOARD_OAUTH_PROVIDERS,
    DEFAULT_OAUTH_ALLOWLIST,
    DEFAULT_OAUTH_PROVIDER,
    DEFAULT_OAUTH_REDIRECT_PATH,
    DashboardAuthConfig,
    DashboardConfig,
    DashboardOAuthConfig,
)
from raft.core.core.errors.cta import OperatorError
from raft.core.platform.locking import DashboardLock

from .oauth_allowlist import DashboardOAuthAllowlist
from .oauth_env import DashboardOAuthEnv
from .settings_write import DashboardSettingsWriter


class DashboardOAuthOps:
    """Create oauth.env template, manage allowlist, readiness checks."""

    def __init__(self, data_home: Path) -> None:
        self._home = data_home
        self._env = DashboardOAuthEnv(data_home)
        self._allow = DashboardOAuthAllowlist(data_home)
        self._writer = DashboardSettingsWriter(data_home)

    def init(
        self,
        *,
        provider: str = DEFAULT_OAUTH_PROVIDER,
        issuer_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        provider = self._require_provider(provider)
        with DashboardLock(self._home):
            cfg = self._writer.load()
            env_path = self._env.write_template(cfg)
            allow = self._allow.ensure(cfg.auth.oauth.allowlist_file)
            next_cfg = self._with_oauth(cfg, provider=provider, issuer_url=issuer_url)
            self._writer.replace(next_cfg)
        return {
            "provider": provider,
            "envFile": str(env_path),
            "allowlistFile": str(allow),
            "redirectUrl": self._env.redirect_url(next_cfg),
            "hint": (
                "Fill OAUTH2_PROXY_CLIENT_ID/SECRET in the env file, "
                "add identities to the allowlist, set "
                "dashboard.auth.mode: oauth and enabled: true in Settings, "
                "then raft render + raft up dashboard"
            ),
        }

    def allowlist_set(self, source: Path) -> Dict[str, Any]:
        cfg = self._writer.load()
        return self._allow.set_from_file(
            source, relative=cfg.auth.oauth.allowlist_file or DEFAULT_OAUTH_ALLOWLIST
        )

    def allowlist_add(self, identity: str) -> Dict[str, Any]:
        cfg = self._writer.load()
        return self._allow.add(
            identity,
            relative=cfg.auth.oauth.allowlist_file or DEFAULT_OAUTH_ALLOWLIST,
        )

    def status_public(self, cfg: Optional[DashboardConfig] = None) -> Dict[str, Any]:
        cfg = cfg or self._writer.load()
        rel = cfg.auth.oauth.allowlist_file
        return {
            "provider": cfg.auth.oauth.provider,
            "issuerUrl": cfg.auth.oauth.issuer_url,
            "redirectPath": cfg.auth.oauth.redirect_path,
            "hasEnvFile": self._env.path().is_file(),
            "hasAllowlist": bool(self._allow.read(rel)),
            "secretsReady": self.secrets_ready(cfg),
        }

    def secrets_ready(self, cfg: Optional[DashboardConfig] = None) -> bool:
        cfg = cfg or self._writer.load()
        return self._env.secrets_present() and self._allow.exists(
            cfg.auth.oauth.allowlist_file
        )

    def require_ready(self, cfg: DashboardConfig) -> None:
        if self.secrets_ready(cfg):
            return
        raise OperatorError(
            "dashboard oauth requires host/secrets/dashboard/oauth.env and allowlist.\n"
            "Fix: write oauth.env with OAUTH2_PROXY_CLIENT_ID, "
            "OAUTH2_PROXY_CLIENT_SECRET, OAUTH2_PROXY_COOKIE_SECRET, "
            "OAUTH2_PROXY_REDIRECT_URL; add identities to the allowlist "
            "file; set auth.mode: oauth in Settings; then raft render "
            "and redeploy dashboard",
            has_fix=False,
        )

    def _with_oauth(
        self,
        cfg: DashboardConfig,
        *,
        provider: str,
        issuer_url: Optional[str],
    ) -> DashboardConfig:
        auth = DashboardAuthConfig(
            mode=cfg.auth.mode,
            password_hash=cfg.auth.password_hash,
            verify_url=cfg.auth.verify_url,
            sign_in_url=cfg.auth.sign_in_url,
            identity_header=cfg.auth.identity_header,
            oauth=self._oauth_cfg(cfg, provider=provider, issuer_url=issuer_url),
        )
        return DashboardConfig(
            enabled=cfg.enabled,
            port=cfg.port,
            public_host=cfg.public_host,
            tls=cfg.tls,
            auth=auth,
        )

    @staticmethod
    def _oauth_cfg(
        cfg: DashboardConfig,
        *,
        provider: str,
        issuer_url: Optional[str],
    ) -> DashboardOAuthConfig:
        prev = cfg.auth.oauth
        issuer = issuer_url if issuer_url is not None else prev.issuer_url
        return DashboardOAuthConfig(
            provider=provider,
            redirect_path=prev.redirect_path or DEFAULT_OAUTH_REDIRECT_PATH,
            allowlist_file=prev.allowlist_file or DEFAULT_OAUTH_ALLOWLIST,
            issuer_url=issuer,
        )

    @staticmethod
    def _require_provider(provider: str) -> str:
        text = (provider or "").strip().lower()
        if text not in DASHBOARD_OAUTH_PROVIDERS:
            raise OperatorError(
                f"dashboard oauth provider must be one of "
                f"{sorted(DASHBOARD_OAUTH_PROVIDERS)}, got {provider!r}.\n"
                "Fix: --provider=google (or oidc)",
                has_fix=False,
            )
        return text
