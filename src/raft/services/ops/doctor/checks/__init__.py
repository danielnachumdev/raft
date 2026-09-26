"""Declarative ordered list of doctor check suites."""

from __future__ import annotations

from .apps import AppChecks, auth_deploy_key_fix
from .base import CheckSuite
from .certs import CertChecks
from .edge import EdgeChecks
from .host import HostChecks
from .ports_summary import PortSummaryChecks
from .public_host import PublicHostChecks
from .runtime import RuntimeChecks
from .upstreams import UpstreamChecks

# Composition order for Doctor.run — add suites here.
CHECK_SUITES: tuple[CheckSuite, ...] = (
    HostChecks(),
    AppChecks(),
    UpstreamChecks(),
    CertChecks(),
    RuntimeChecks(),
    EdgeChecks(),
    PortSummaryChecks(),
    PublicHostChecks(),
)

__all__ = [
    "CHECK_SUITES",
    "CheckSuite",
    "AppChecks",
    "CertChecks",
    "EdgeChecks",
    "HostChecks",
    "PortSummaryChecks",
    "PublicHostChecks",
    "RuntimeChecks",
    "UpstreamChecks",
    "auth_deploy_key_fix",
]
