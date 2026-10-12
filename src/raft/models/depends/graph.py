"""Transitive ``spec.dependsOn`` order for wake / heal / co-stop."""

from typing import Mapping, Sequence, Union

from .error import DependsOnError
from .spec import DependsOnSpec


class AppDependsGraph:
    """Directed graph of app names → direct ``dependsOn`` edges."""

    def __init__(self, edges: Mapping[str, Sequence[Union[str, DependsOnSpec]]]) -> None:
        self._edges: dict[str, tuple[DependsOnSpec, ...]] = {
            name: tuple(self._coerce(dep) for dep in deps) for name, deps in edges.items()
        }

    def before(self, name: str) -> tuple[str, ...]:
        """Transitive deps of ``name`` in start order (deps first), excluding ``name``."""
        return self._walk(name, scale_only=False)

    def costop_before(self, name: str) -> tuple[str, ...]:
        """Transitive deps reached only via ``scaleWithParent: true`` edges."""
        return self._walk(name, scale_only=True)

    def wake_chain(self, name: str) -> tuple[str, ...]:
        """``before(name)`` then ``name`` — start order for wake / heal."""
        return self.before(name) + (name,)

    def assert_acyclic(self) -> None:
        """Raise ``DependsOnError`` if any directed cycle exists among known nodes."""
        done: set[str] = set()
        for name in sorted(self._edges):
            if name in done:
                continue
            visiting: set[str] = set()
            order: list[str] = []
            self._visit(name, visiting, done, order, scale_only=False)

    def _walk(self, name: str, *, scale_only: bool) -> tuple[str, ...]:
        self._require_known(name)
        order: list[str] = []
        visiting: set[str] = set()
        done: set[str] = set()
        for dep in self._edges[name]:
            if scale_only and not dep.scale_with_parent:
                continue
            self._visit(dep.name, visiting, done, order, scale_only=scale_only)
        return tuple(order)

    def _require_known(self, name: str) -> None:
        if name not in self._edges:
            raise DependsOnError(f"unknown app in dependsOn graph: {name!r}")

    def _visit(
        self,
        name: str,
        visiting: set[str],
        done: set[str],
        order: list[str],
        *,
        scale_only: bool,
    ) -> None:
        if name in done:
            return
        self._require_known(name)
        if name in visiting:
            raise DependsOnError(f"dependsOn cycle involving {name!r}")
        visiting.add(name)
        for dep in self._edges[name]:
            if scale_only and not dep.scale_with_parent:
                continue
            self._visit(dep.name, visiting, done, order, scale_only=scale_only)
        visiting.discard(name)
        done.add(name)
        order.append(name)

    @staticmethod
    def _coerce(dep: Union[str, DependsOnSpec]) -> DependsOnSpec:
        if isinstance(dep, DependsOnSpec):
            return dep
        return DependsOnSpec(name=str(dep), scale_with_parent=True)
