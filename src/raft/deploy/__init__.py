from __future__ import annotations

"""Deploy: orchestrate, cutover, locks, and readiness."""

from typing import Any

from ..utils.package_exports import PackageExports

__all__ = [
    "CutoverSession",
    "DEPLOY_CUTOVER",
    "DeploymentContext",
    "DeploymentMethod",
    "DeploymentMethodCatalogs",
    "DeploymentMethodRegistry",
    "DualRunCutover",
    "InPlaceDeployment",
    "Orchestrator",
    "ReadinessStrategy",
    "SeamlessDeployment",
    "StackUpScalePlan",
    "WaitUntil",
]

_EXPORTS = PackageExports(
    __name__,
    {
        "CutoverSession": ".cutover:CutoverSession",
        "DEPLOY_CUTOVER": ".cutover:DEPLOY_CUTOVER",
        "DeploymentContext": ".methods:DeploymentContext",
        "DeploymentMethod": ".methods:DeploymentMethod",
        "DeploymentMethodCatalogs": ".methods:DeploymentMethodCatalogs",
        "DeploymentMethodRegistry": ".methods:DeploymentMethodRegistry",
        "DualRunCutover": ".dual_run:DualRunCutover",
        "InPlaceDeployment": ".methods:InPlaceDeployment",
        "Orchestrator": ".orchestrator:Orchestrator",
        "ReadinessStrategy": ".readiness:ReadinessStrategy",
        "SeamlessDeployment": ".methods:SeamlessDeployment",
        "StackUpScalePlan": ".up_scale_plan:StackUpScalePlan",
        "WaitUntil": ".wait:WaitUntil",
    },
)


def __getattr__(name: str) -> Any:
    value = _EXPORTS.get(name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
