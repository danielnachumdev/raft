"""Parse ``dashboard:`` from settings.yaml."""

from typing import Any

from raft.core.core.errors.cta import OperatorError

from ..dashboard_config import (
    DASHBOARD_AUTH_MODES,
    DASHBOARD_OAUTH_PROVIDERS,
    DASHBOARD_TLS_MODES,
    DEFAULT_DASHBOARD_AUTH_MODE,
    DEFAULT_DASHBOARD_ENABLED,
    DEFAULT_DASHBOARD_PORT,
    DEFAULT_DASHBOARD_TLS,
    DEFAULT_IDENTITY_HEADER,
    DEFAULT_OAUTH_ALLOWLIST,
    DEFAULT_OAUTH_PROVIDER,
    DEFAULT_OAUTH_REDIRECT_PATH,
    DashboardAuthConfig,
    DashboardConfig,
    DashboardOAuthConfig,
)
from ..scalars import SettingsScalars
from ..section import SettingsSectionParser


class DashboardSettingsParser(SettingsSectionParser[DashboardConfig]):
    """Validate and build :class:`DashboardConfig`."""

    def __init__(self) -> None:
        self._scalars = SettingsScalars()

    def parse(self, raw: Any) -> DashboardConfig:
        if raw is None:
            return DashboardConfig()
        if not isinstance(raw, dict):
            raise self._not_mapping()
        cfg = DashboardConfig(
            enabled=bool(raw.get("enabled", DEFAULT_DASHBOARD_ENABLED)),
            port=self._port(raw),
            public_host=self._scalars.optional_str(raw.get("publicHost")),
            tls=self._tls(raw.get("tls")),
            auth=self._auth(raw.get("auth")),
        )
        self._validate(cfg)
        return cfg

    def _port(self, raw: dict) -> int:
        return self._scalars.pos_int(raw, "port", DEFAULT_DASHBOARD_PORT, "dashboard")

    def _tls(self, raw: Any) -> str:
        if raw is None:
            return DEFAULT_DASHBOARD_TLS
        text = str(raw).strip().lower()
        if text not in DASHBOARD_TLS_MODES:
            raise OperatorError(
                f"settings.yaml dashboard.tls must be one of "
                f"{sorted(DASHBOARD_TLS_MODES)}, got {raw!r}.\n"
                f"Fix: set dashboard.tls: acme (or off|origin)",
                has_fix=False,
            )
        return text

    def _auth(self, raw: Any) -> DashboardAuthConfig:
        if raw is None:
            return DashboardAuthConfig()
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml dashboard.auth must be a mapping.\n"
                "Fix: set dashboard.auth: {mode: password}",
                has_fix=False,
            )
        return DashboardAuthConfig(
            mode=self._auth_mode(raw.get("mode")),
            password_hash=self._scalars.optional_str(raw.get("passwordHash")),
            verify_url=self._scalars.optional_str(raw.get("verifyUrl")),
            sign_in_url=self._scalars.optional_str(raw.get("signInUrl")),
            identity_header=self._identity_header(raw.get("identityHeader")),
            oauth=self._oauth(raw.get("oauth")),
        )

    def _oauth(self, raw: Any) -> DashboardOAuthConfig:
        if raw is None:
            return DashboardOAuthConfig()
        if not isinstance(raw, dict):
            raise OperatorError(
                "settings.yaml dashboard.auth.oauth must be a mapping.\n"
                "Fix: set dashboard.auth.oauth: {provider: google}",
                has_fix=False,
            )
        return DashboardOAuthConfig(
            provider=self._oauth_provider(raw.get("provider")),
            redirect_path=self._redirect_path(raw.get("redirectPath")),
            allowlist_file=self._allowlist(raw.get("allowlistFile")),
            issuer_url=self._scalars.optional_str(raw.get("issuerUrl")),
        )

    def _auth_mode(self, raw: Any) -> str:
        if raw is None:
            return DEFAULT_DASHBOARD_AUTH_MODE
        text = str(raw).strip().lower()
        if text not in DASHBOARD_AUTH_MODES:
            raise OperatorError(
                f"settings.yaml dashboard.auth.mode must be one of "
                f"{sorted(DASHBOARD_AUTH_MODES)}, got {raw!r}.\n"
                f"Fix: set dashboard.auth.mode: password",
                has_fix=False,
            )
        return text

    def _oauth_provider(self, raw: Any) -> str:
        if raw is None:
            return DEFAULT_OAUTH_PROVIDER
        text = str(raw).strip().lower()
        if text not in DASHBOARD_OAUTH_PROVIDERS:
            raise OperatorError(
                f"settings.yaml dashboard.auth.oauth.provider must be one of "
                f"{sorted(DASHBOARD_OAUTH_PROVIDERS)}, got {raw!r}.\n"
                f"Fix: set provider: google (or oidc)",
                has_fix=False,
            )
        return text

    def _redirect_path(self, raw: Any) -> str:
        text = self._scalars.optional_str(raw)
        return text or DEFAULT_OAUTH_REDIRECT_PATH

    def _allowlist(self, raw: Any) -> str:
        text = self._scalars.optional_str(raw)
        return text or DEFAULT_OAUTH_ALLOWLIST

    def _identity_header(self, raw: Any) -> str:
        text = self._scalars.optional_str(raw)
        return text or DEFAULT_IDENTITY_HEADER

    def _validate(self, cfg: DashboardConfig) -> None:
        if cfg.auth.mode == "none" and cfg.is_public():
            raise OperatorError(
                "settings.yaml dashboard: auth.mode none cannot set publicHost.\n"
                "Fix: set auth.mode to password, oauth, or external",
                has_fix=False,
            )
        self._validate_external(cfg)
        self._validate_oauth(cfg)

    def _validate_external(self, cfg: DashboardConfig) -> None:
        if cfg.auth.mode != "external":
            return
        if not cfg.auth.verify_url or not cfg.auth.sign_in_url:
            raise OperatorError(
                "settings.yaml dashboard.auth.mode external requires "
                "verifyUrl and signInUrl.\n"
                "Fix: set dashboard.auth.verifyUrl and signInUrl",
                has_fix=False,
            )

    def _validate_oauth(self, cfg: DashboardConfig) -> None:
        if cfg.auth.mode != "oauth":
            return
        if cfg.auth.oauth.provider == "oidc" and not cfg.auth.oauth.issuer_url:
            raise OperatorError(
                "dashboard.auth.oauth.provider oidc requires issuerUrl.\n"
                "Fix: set dashboard.auth.oauth.issuerUrl",
                has_fix=False,
            )

    @staticmethod
    def _not_mapping() -> OperatorError:
        return OperatorError(
            "settings.yaml dashboard must be a mapping.\n"
            "Fix: set dashboard: {enabled: true, port: 8787}",
            has_fix=False,
        )
