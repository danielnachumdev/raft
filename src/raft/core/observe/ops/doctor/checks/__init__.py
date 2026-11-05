"""Declarative ordered list of doctor check suites."""

from __future__ import annotations

from .alerts import AlertsChecks
from .apps import AppChecks
from .base import CheckSuite
from .certs import CertChecks
from .dashboard_oauth import DashboardOauthChecks
from .edge import EdgeChecks
from .env_file import EnvFileChecks
from .host import HostChecks
from .ports_summary import PortSummaryChecks
from .public_host import PublicHostChecks
from .runtime import RuntimeChecks
from .upstreams import UpstreamChecks

# GitopsChecks imports alert loaders; keep it out of this module's eager import
# graph so ``observe.alerts.catalogs`` can finish initializing.


def check_suites() -> tuple[CheckSuite, ...]:
    from .gitops import GitopsChecks

    return (
        HostChecks(),
        GitopsChecks(),
        AppChecks(),
        EnvFileChecks(),
        UpstreamChecks(),
        CertChecks(),
        RuntimeChecks(),
        EdgeChecks(),
        PortSummaryChecks(),
        PublicHostChecks(),
        DashboardOauthChecks(),
        AlertsChecks(),
    )


__all__ = [
    "CheckSuite",
    "AlertsChecks",
    "AppChecks",
    "CertChecks",
    "DashboardOauthChecks",
    "EdgeChecks",
    "EnvFileChecks",
    "HostChecks",
    "PortSummaryChecks",
    "PublicHostChecks",
    "RuntimeChecks",
    "UpstreamChecks",
    "check_suites",
]
