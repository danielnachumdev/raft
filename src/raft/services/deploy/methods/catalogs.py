"""Shipped deployment method catalogs (composition root)."""

from __future__ import annotations

from .inplace import InPlaceDeployment
from .registry import DeploymentMethodRegistry
from .seamless import SeamlessDeployment


class DeploymentMethodCatalogs:
    """Register concrete strategies. Add methods here — do not branch in callers."""

    @staticmethod
    def default() -> DeploymentMethodRegistry:
        registry = DeploymentMethodRegistry()
        registry.register(SeamlessDeployment())
        registry.register(InPlaceDeployment())
        return registry
