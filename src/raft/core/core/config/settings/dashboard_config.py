"""Always-on ``raft-dashboard`` settings (Compose service + optional public Host)."""

from dataclasses import dataclass, field
from typing import Optional

DEFAULT_DASHBOARD_ENABLED = False
DEFAULT_DASHBOARD_PORT = 8787
DEFAULT_DASHBOARD_TLS = "off"
DEFAULT_DASHBOARD_AUTH_MODE = "none"
DEFAULT_IDENTITY_HEADER = "X-Raft-Identity"
DEFAULT_OAUTH_PROVIDER = "google"
DEFAULT_OAUTH_REDIRECT_PATH = "/oauth2/callback"
DEFAULT_OAUTH_ALLOWLIST = "secrets/dashboard/oauth-allowlist.txt"

DASHBOARD_TLS_MODES = frozenset({"off", "origin", "acme"})
DASHBOARD_AUTH_MODES = frozenset({"none", "password", "external", "oauth"})
DASHBOARD_OAUTH_PROVIDERS = frozenset({"google", "oidc"})
DASHBOARD_SERVICE_NAME = "raft-dashboard"


@dataclass(frozen=True)
class DashboardOAuthConfig:
    """First-party OAuth edge (provider catalog — not Google-only)."""

    provider: str = DEFAULT_OAUTH_PROVIDER
    redirect_path: str = DEFAULT_OAUTH_REDIRECT_PATH
    allowlist_file: str = DEFAULT_OAUTH_ALLOWLIST
    issuer_url: Optional[str] = None  # required when provider=oidc


@dataclass(frozen=True)
class DashboardAuthConfig:
    """Auth for the always-on dashboard process / public Host."""

    mode: str = DEFAULT_DASHBOARD_AUTH_MODE
    password_hash: Optional[str] = None
    verify_url: Optional[str] = None
    sign_in_url: Optional[str] = None
    identity_header: str = DEFAULT_IDENTITY_HEADER
    oauth: DashboardOAuthConfig = field(default_factory=DashboardOAuthConfig)


@dataclass(frozen=True)
class DashboardConfig:
    """``settings.yaml`` ``dashboard:`` — opt-in always-on ops UI."""

    enabled: bool = DEFAULT_DASHBOARD_ENABLED
    port: int = DEFAULT_DASHBOARD_PORT
    public_host: Optional[str] = None
    tls: str = DEFAULT_DASHBOARD_TLS
    auth: DashboardAuthConfig = field(default_factory=DashboardAuthConfig)

    def is_public(self) -> bool:
        return bool(self.public_host and str(self.public_host).strip())

    def requires_password_hash(self) -> bool:
        return self.is_public() and self.auth.mode == "password"

    def uses_identity_header(self) -> bool:
        return self.auth.mode in {"external", "oauth"}
