from __future__ import annotations

"""ACME TLS paths, issue/install, and HTTP→HTTPS redirect helpers."""

from typing import Any

from ..utils.package_exports import PackageExports

__all__ = [
    "AcmeAccountStore",
    "AcmeAppState",
    "AcmeAppStore",
    "AcmeCertMaterial",
    "AcmeCertWriter",
    "AcmeEnsure",
    "AcmeGateInstall",
    "AcmeHttp01Webroot",
    "AcmeHttpRedirect",
    "AcmeOrderRunner",
    "AcmePaths",
]

_EXPORTS = PackageExports(
    __name__,
    {
        "AcmeAccountStore": ".account:AcmeAccountStore",
        "AcmeAppState": ".app_store:AcmeAppState",
        "AcmeAppStore": ".app_store:AcmeAppStore",
        "AcmeCertMaterial": ".material:AcmeCertMaterial",
        "AcmeCertWriter": ".material:AcmeCertWriter",
        "AcmeEnsure": ".ensure:AcmeEnsure",
        "AcmeGateInstall": ".install:AcmeGateInstall",
        "AcmeHttp01Webroot": ".webroot:AcmeHttp01Webroot",
        "AcmeHttpRedirect": ".http_redirect:AcmeHttpRedirect",
        "AcmeOrderRunner": ".order:AcmeOrderRunner",
        "AcmePaths": ".paths:AcmePaths",
    },
)


def __getattr__(name: str) -> Any:
    value = _EXPORTS.get(name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
