"""Render oauth2-proxy config for a catalog provider (google | oidc)."""

from typing import Optional

from raft.core.core.config.settings.dashboard_config import DashboardConfig
from raft.core.core.errors.cta import OperatorError

from .oauth_paths import OAUTH_PROXY_PORT


class DashboardOAuthProxyCfg:
    """Provider-specific oauth2-proxy.cfg body (secrets via env)."""

    def render(self, cfg: DashboardConfig) -> str:
        oauth = cfg.auth.oauth
        provider_lines = self._provider_lines(oauth.provider, oauth.issuer_url)
        allow = self._container_allowlist(oauth.allowlist_file)
        return "\n".join(self._common(allow, provider_lines)) + "\n"

    def _provider_lines(self, provider: str, issuer_url: Optional[str]) -> list[str]:
        if provider == "google":
            return self._google()
        if provider == "oidc":
            return self._oidc(issuer_url)
        raise OperatorError(
            f"unsupported dashboard oauth provider {provider!r}.\n"
            f"Fix: set dashboard.auth.oauth.provider to google or oidc",
            has_fix=False,
        )

    @staticmethod
    def _common(allow: str, provider_lines: list[str]) -> list[str]:
        return [
            f'http_address = "127.0.0.1:{OAUTH_PROXY_PORT}"',
            "reverse_proxy = true",
            *provider_lines,
            f'authenticated_emails_file = "{allow}"',
            "email_domains = []",
            'upstreams = [ "static://202" ]',
            "set_xauthrequest = true",
            "set_authorization_header = false",
            "pass_access_token = false",
            *DashboardOAuthProxyCfg._cookie_lines(),
            'prompt = "select_account"',
            "skip_provider_button = true",
            "silence_ping_logging = true",
        ]

    @staticmethod
    def _cookie_lines() -> list[str]:
        return [
            "cookie_httponly = true",
            'cookie_samesite = "lax"',
            "cookie_secure = true",
            "cookie_csrf_per_request = true",
            'cookie_csrf_expire = "5m"',
        ]

    @staticmethod
    def _google() -> list[str]:
        return ['provider = "google"']

    @staticmethod
    def _oidc(issuer_url: Optional[str]) -> list[str]:
        if not issuer_url:
            raise OperatorError(
                "dashboard oauth provider oidc requires issuerUrl.\n"
                "Fix: set dashboard.auth.oauth.issuerUrl",
                has_fix=False,
            )
        return [
            'provider = "oidc"',
            f'oidc_issuer_url = "{issuer_url}"',
        ]

    @staticmethod
    def _container_allowlist(relative: str) -> str:
        # Compose mounts data home at /raft.
        text = relative.strip().lstrip("/")
        return f"/raft/{text}"
