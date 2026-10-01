"""Transitive ``spec.dependsOn`` order for wake / heal (Compose uses render)."""

from __future__ import annotations

from typing import Dict, Mapping, Sequence, Set, Tuple

__all__ = ["AppDependsGraph", "DependsOnError"]


class DependsOnError(ValueError):
    """Cycle or missing name in a ``dependsOn`` graph."""


class AppDependsGraph:
    """Directed graph of app names → direct ``dependsOn`` edges."""

    def __init__(self, edges: Mapping[str, Sequence[str]]) -> None:
        self._edges: Dict[str, Tuple[str, ...]] = {
            name: tuple(deps) for name, deps in edges.items()
        }

    def before(self, name: str) -> Tuple[str, ...]:
        """Transitive deps of ``name`` in start order (deps first), excluding ``name``."""
        self._require_known(name)
        order: list[str] = []
        visiting: Set[str] = set()
        done: Set[str] = set()
        for dep in self._edges[name]:
            self._visit(dep, visiting, done, order)
        return tuple(order)

    def wake_chain(self, name: str) -> Tuple[str, ...]:
        """``before(name)`` then ``name`` — start order for wake / heal."""
        return self.before(name) + (name,)

    def _require_known(self, name: str) -> None:
        if name not in self._edges:
            raise DependsOnError(f"unknown app in dependsOn graph: {name!r}")

    def _visit(
        self,
        name: str,
        visiting: Set[str],
        done: Set[str],
        order: list[str],
    ) -> None:
        if name in done:
            return
        self._require_known(name)
        if name in visiting:
            raise DependsOnError(f"dependsOn cycle involving {name!r}")
        visiting.add(name)
        for dep in self._edges[name]:
            self._visit(dep, visiting, done, order)
        visiting.discard(name)
        done.add(name)
        order.append(name)
