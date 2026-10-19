"""Always-on ``raft-dashboard`` settings (Compose service + optional public Host)."""

from dataclasses import dataclass, field
from typing import Optional

DEFAULT_DASHBOARD_ENABLED = False
DEFAULT_DASHBOARD_PORT = 8787
DEFAULT_DASHBOARD_TLS = "off"
DEFAULT_DASHBOARD_AUTH_MODE = "none"
DEFAULT_IDENTITY_HEADER = "X-Raft-Identity"

DASHBOARD_TLS_MODES = frozenset({"off", "origin", "acme"})
DASHBOARD_AUTH_MODES = frozenset({"none", "password", "external"})
DASHBOARD_SERVICE_NAME = "raft-dashboard"


@dataclass(frozen=True)
class DashboardAuthConfig:
    """Auth for the always-on dashboard process / public Host."""

    mode: str = DEFAULT_DASHBOARD_AUTH_MODE
    password_hash: Optional[str] = None
    verify_url: Optional[str] = None
    sign_in_url: Optional[str] = None
    identity_header: str = DEFAULT_IDENTITY_HEADER


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
