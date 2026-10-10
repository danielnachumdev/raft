from __future__ import annotations

"""Operator ops: doctor, status, logs, certs, purge, update, uninstall."""

from typing import Any

from ..utils.package_exports import PackageExports

__all__ = [
    "AcmeCertHealth",
    "CertProbe",
    "Doctor",
    "Logs",
    "MissingAcmeCerts",
    "MissingOriginCerts",
    "Purge",
    "PurgeResult",
    "SelfUpdate",
    "Status",
    "Uninstall",
]

_EXPORTS = PackageExports(
    __name__,
    {
        "AcmeCertHealth": ".acme_health:AcmeCertHealth",
        "CertProbe": ".certs:CertProbe",
        "Doctor": ".doctor:Doctor",
        "Logs": ".logs:Logs",
        "MissingAcmeCerts": ".certs:MissingAcmeCerts",
        "MissingOriginCerts": ".certs:MissingOriginCerts",
        "Purge": ".purge:Purge",
        "PurgeResult": ".purge:PurgeResult",
        "SelfUpdate": ".update:SelfUpdate",
        "Status": ".status:Status",
        "Uninstall": ".uninstall:Uninstall",
    },
)


def __getattr__(name: str) -> Any:
    value = _EXPORTS.get(name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
