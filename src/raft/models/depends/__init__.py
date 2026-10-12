"""Transitive ``spec.dependsOn`` graph for wake / heal / co-stop."""

from .error import DependsOnError
from .graph import AppDependsGraph
from .spec import DependsOnSpec

__all__ = ["AppDependsGraph", "DependsOnError", "DependsOnSpec"]
