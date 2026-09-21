"""Declarative ordered list of doctor check suites."""

from __future__ import annotations

from .apps import AppChecks, auth_deploy_key_fix
from .certs import CertChecks
from .edge import EdgeChecks
from .host import HostChecks
from .runtime import RuntimeChecks
from .upstreams import UpstreamChecks

# Composition order for Doctor.run — add suites here.
CHECK_SUITES = (
    HostChecks(),
    AppChecks(),
    UpstreamChecks(),
    CertChecks(),
    RuntimeChecks(),
    EdgeChecks(),
)

__all__ = [
    "CHECK_SUITES",
    "AppChecks",
    "CertChecks",
    "EdgeChecks",
    "HostChecks",
    "RuntimeChecks",
    "UpstreamChecks",
    "auth_deploy_key_fix",
]
