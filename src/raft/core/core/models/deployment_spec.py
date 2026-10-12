"""Per-app deploy transition contract (``spec.deployment``)."""

from dataclasses import dataclass

DEFAULT_DEPLOYMENT_METHOD = "seamless"
DEPLOYMENT_METHODS = frozenset({"seamless", "inplace"})


@dataclass(frozen=True)
class DeploymentSpec:
    """How apply/redeploy replaces a running generation. Default method is seamless."""

    method: str = DEFAULT_DEPLOYMENT_METHOD
