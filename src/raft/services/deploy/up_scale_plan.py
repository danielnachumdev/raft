"""Which apps stay scaled-to-zero on ``raft up`` (pull images, do not start)."""

from __future__ import annotations

import logging
from typing import AbstractSet, Dict, Optional, Tuple

from raft.errors import OperatorError
from raft.models.app import App
from raft.models.app_document import AppDocument
from raft.models.depends import AppDependsGraph, DependsOnError, DependsOnSpec
from raft.models.manifest import AppSpec
from raft.models.registry import AppRegistry
from raft.models.scaling_store import ScalingStore
from raft.models.stack import Stack

logger = logging.getLogger(__name__)


class StackUpScalePlan:
    """Map scale-to-zero apps (+ costop deps) to pull vs start sets for cold up."""

    def __init__(self, stack: Stack) -> None:
        self.stack = stack
        self._deferred = self._compute_deferred()

    def has_deferred(self) -> bool:
        return bool(self._deferred)

    def deferred_compose_ids(self) -> Tuple[str, ...]:
        return self._compose_ids(self._deferred)

    def deferred_pull_compose_ids(self) -> Tuple[str, ...]:
        """Image-backed deferred apps (``source=docker``) — ``compose pull`` only."""
        return self._compose_ids(self._deferred_by_source("docker"))

    def deferred_build_compose_ids(self) -> Tuple[str, ...]:
        """Git/local deferred apps — ``compose build`` only (avoids empty-build WARN)."""
        names = {
            app.name
            for app in self.stack.apps
            if app.name in self._deferred and app.source != "docker"
        }
        return self._compose_ids(names)

    def start_compose_ids(self) -> Tuple[str, ...]:
        return (
            self.stack.gate,
            self.stack.router,
            self.stack.controller,
            *(app.compose_id for app in self.apps_to_start()),
        )

    def _deferred_by_source(self, source: str) -> AbstractSet[str]:
        return {
            app.name
            for app in self.stack.apps
            if app.name in self._deferred and app.source == source
        }

    def _compose_ids(self, names: AbstractSet[str]) -> Tuple[str, ...]:
        by_name = {app.name: app.compose_id for app in self.stack.apps}
        return tuple(by_name[name] for name in sorted(names) if name in by_name)

    def apps_to_start(self) -> Tuple[App, ...]:
        return tuple(app for app in self.stack.apps if app.name not in self._deferred)

    def mark_scaled_to_zero(self) -> None:
        store = ScalingStore(self.stack.root)
        for name in sorted(self._deferred):
            store.mark_scaled_to_zero(name)

    def _compute_deferred(self) -> frozenset[str]:
        names: set[str] = set()
        graph = AppDependsGraph(self._depends_edges())
        for app in self.stack.apps:
            if not self._has_scaling(app):
                continue
            names.add(app.name)
            names.update(self._costop_names(graph, app.name))
        return frozenset(names)

    def _costop_names(self, graph: AppDependsGraph, name: str) -> Tuple[str, ...]:
        try:
            return graph.costop_before(name)
        except DependsOnError as exc:
            logger.error("raft up scale plan dependsOn app=%s: %s", name, exc)
            return ()

    def _depends_edges(self) -> Dict[str, Tuple[DependsOnSpec, ...]]:
        edges: Dict[str, Tuple[DependsOnSpec, ...]] = {}
        for app in self.stack.apps:
            spec = self._load_spec(app)
            edges[app.name] = () if spec is None else spec.depends_on
        return edges

    def _has_scaling(self, app: App) -> bool:
        spec = self._load_spec(app)
        return spec is not None and spec.scaling is not None

    def _load_spec(self, app: App) -> Optional[AppSpec]:
        path = AppRegistry(self.stack.root).path_for(app.name)
        if not path.is_file():
            return None
        try:
            _, spec = AppDocument.load(path, expect_name=app.name)
        except (OSError, ValueError, OperatorError):
            return None
        return spec
