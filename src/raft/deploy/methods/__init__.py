"""DeploymentMethod ABC and registry types.

Concrete strategies and catalogs import cutover/render — import them from
``methods.catalogs`` / ``methods.strategies`` so package-type imports stay light.
"""

from .method import DeploymentContext, DeploymentMethod
from .registry import DeploymentMethodRegistry

__all__ = [
    "DeploymentContext",
    "DeploymentMethod",
    "DeploymentMethodRegistry",
]
