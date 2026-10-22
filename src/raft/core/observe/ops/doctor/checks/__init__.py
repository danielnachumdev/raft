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

# Composition order for Doctor.run — add suites here.
CHECK_SUITES: tuple[CheckSuite, ...] = (
    HostChecks(),
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
    "CHECK_SUITES",
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
]
