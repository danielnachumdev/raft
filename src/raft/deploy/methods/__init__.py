from __future__ import annotations

"""Pluggable app DeploymentMethod strategies (seamless / inplace)."""

from typing import Any

from ...utils.package_exports import PackageExports

__all__ = [
    "DeploymentContext",
    "DeploymentMethod",
    "DeploymentMethodCatalogs",
    "DeploymentMethodRegistry",
    "InPlaceDeployment",
    "SeamlessDeployment",
]

_EXPORTS = PackageExports(
    __name__,
    {
        "DeploymentContext": ".method:DeploymentContext",
        "DeploymentMethod": ".method:DeploymentMethod",
        "DeploymentMethodCatalogs": ".catalogs:DeploymentMethodCatalogs",
        "DeploymentMethodRegistry": ".registry:DeploymentMethodRegistry",
        "InPlaceDeployment": ".strategies:InPlaceDeployment",
        "SeamlessDeployment": ".strategies:SeamlessDeployment",
    },
)


def __getattr__(name: str) -> Any:
    value = _EXPORTS.get(name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
