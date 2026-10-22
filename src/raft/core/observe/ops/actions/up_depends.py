"""Bring up transitive ``spec.dependsOn`` before an operator App up (wake order)."""

from typing import Dict, Optional, Tuple

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app_document import AppDocument
from raft.core.core.models.depends import AppDependsGraph, DependsOnError, DependsOnSpec
from raft.core.core.models.registry import AppRegistry
from raft.core.core.models.stack import Stack
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.platform.adapters.docker import DockerStack
from raft.core.platform.adapters.nginx import NginxUpstreams

__all__ = ["UpDepends"]


class UpDepends:
    """Resolve and bring up the wake ``dependsOn`` chain for operator up."""

    def __init__(self, stack: Stack, docker: DockerStack) -> None:
        self.stack = stack
        self.docker = docker

    def wake_chain(self, name: str) -> Tuple[str, ...]:
        """Deps-first up order including ``name`` (same as scale wake)."""
        try:
            return AppDependsGraph(self.depends_edges()).wake_chain(name)
        except DependsOnError as exc:
            raise OperatorError(
                f"cannot bring up {name!r}: dependsOn graph error: {exc}",
                has_fix=False,
            ) from exc

    def depends_edges(self) -> Dict[str, Tuple[DependsOnSpec, ...]]:
        edges: Dict[str, Tuple[DependsOnSpec, ...]] = {}
        for app in self.stack.apps:
            edges[app.name] = self._edges_for(app.name)
        return edges

    def up_dep(self, name: str) -> str:
        """Bring up one dependency Compose service; return its compose id."""
        compose_id = self._compose_id(name)
        if compose_id is None:
            raise OperatorError(
                f"cannot bring up dependency {name!r}: not in applied apps",
                has_fix=False,
            )
        self.docker.start_service(compose_id)
        ScalingStore(self.stack.root).clear_scaled_to_zero(name)
        return compose_id

    def restore_upstreams(self, names: Tuple[str, ...]) -> None:
        """Point HTTP upstreams at Compose hostnames after bringing up a chain."""
        nginx = NginxUpstreams(self.stack, self.docker)
        by_name = {app.name: app for app in self.stack.apps}
        for name in names:
            app = by_name.get(name)
            if app is not None:
                nginx.point_steady(app, reload=False)

    def _edges_for(self, name: str) -> Tuple[DependsOnSpec, ...]:
        path = AppRegistry(self.stack.root).path_for(name)
        if not path.is_file():
            return ()
        try:
            _, spec = AppDocument.load(path, expect_name=name)
        except (OSError, ValueError, OperatorError):
            return ()
        return spec.depends_on

    def _compose_id(self, name: str) -> Optional[str]:
        for app in self.stack.apps:
            if app.name == name:
                return app.compose_id
        return None
