"""Fail closed on cyclic ``spec.dependsOn`` at apply (before registry write)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

from raft.errors.cta import OperatorError
from raft.errors.domain import depends_on_cycle

from .app_document import AppDocument
from .depends import AppDependsGraph, DependsOnError, DependsOnSpec
from .registry import AppRegistry

__all__ = ["DependsOnCycleGuard"]


class DependsOnCycleGuard:
    """Build a prospective dependsOn graph and reject directed cycles."""

    def __init__(self, home: Path) -> None:
        self.home = home

    def reject(self, name: str, depends_on: tuple[DependsOnSpec, ...]) -> None:
        edges = self._prospective_edges(name, depends_on)
        try:
            AppDependsGraph(edges).assert_acyclic()
        except DependsOnError as exc:
            raise depends_on_cycle(name, str(exc)) from exc

    def _prospective_edges(
        self, name: str, depends_on: tuple[DependsOnSpec, ...]
    ) -> Dict[str, Tuple[DependsOnSpec, ...]]:
        edges: Dict[str, Tuple[DependsOnSpec, ...]] = {}
        for app in AppRegistry(self.home).load():
            if app.name == name:
                continue
            edges[app.name] = self._edges_for(app.name)
        edges[name] = depends_on
        known = set(edges)
        return {
            node: tuple(dep for dep in deps if dep.name in known)
            for node, deps in edges.items()
        }

    def _edges_for(self, app_name: str) -> Tuple[DependsOnSpec, ...]:
        path = AppRegistry(self.home).path_for(app_name)
        if not path.is_file():
            return ()
        try:
            _, spec = AppDocument.load(path, expect_name=app_name)
        except (OSError, ValueError, OperatorError):
            return ()
        return spec.depends_on
