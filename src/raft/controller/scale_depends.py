"""dependsOn helpers for Scaler idle co-stop and wake start order."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from raft.adapters.docker import DockerStack
from raft.errors import OperatorError
from raft.models.app_document import AppDocument
from raft.models.depends import AppDependsGraph, DependsOnError, DependsOnSpec
from raft.models.graph_event_store import SCALING_ACTION_IDLE_STOP, GraphEventStore
from raft.models.manifest import AppSpec
from raft.models.registry import AppRegistry
from raft.models.scaling_store import ScalingStore
from raft.models.stack import Stack
from raft.services.deploy.locking import apps_and_stack_locks

__all__ = ["ScaleDepends"]

logger = logging.getLogger(__name__)

SleepFn = Callable[[float], None]
_WAKE_POLL_SECONDS = 0.2


class ScaleDepends:
    """Resolve dependsOn graphs; idle-stop co-deps; start wake chains."""

    def __init__(
        self,
        home: Path,
        docker: DockerStack,
        store: ScalingStore,
        *,
        clock: Callable[[], float],
        sleep: SleepFn,
    ) -> None:
        self.home = home
        self.docker = docker
        self.store = store
        self._clock = clock
        self._sleep = sleep

    def idle_stop(self, name: str, compose_id: str) -> None:
        costop = self.costop_deps(name)
        if costop is None:
            return
        # Reverse of wake start order: stop the scaled parent first, then co-deps.
        order = (name,) + tuple(reversed(costop))
        logger.info("scale idle-stop app=%s chain=%s", name, ",".join(order))
        try:
            with apps_and_stack_locks(self.home, order):
                self._stop_scaled_chain(order, parent=name, parent_compose=compose_id)
        except OperatorError as exc:
            logger.error("scale idle-stop failed app=%s: %s", name, exc)
            return
        self._record_idle_stop_event(name, compose_id)
        logger.info("scale idle-stop ok app=%s", name)

    def costop_deps(self, name: str) -> Optional[Tuple[str, ...]]:
        try:
            return AppDependsGraph(self.depends_edges()).costop_before(name)
        except DependsOnError as exc:
            logger.error("scale idle-stop dependsOn app=%s: %s", name, exc)
            return None

    def wake_chain(self, name: str) -> Optional[Tuple[str, ...]]:
        try:
            return AppDependsGraph(self.depends_edges()).wake_chain(name)
        except DependsOnError as exc:
            logger.error("scale wake dependsOn app=%s: %s", name, exc)
            return None

    def depends_edges(self) -> Dict[str, Tuple[DependsOnSpec, ...]]:
        edges: Dict[str, Tuple[DependsOnSpec, ...]] = {}
        for app in Stack.load_apps(self.home).apps:
            spec = self.load_spec(app.name)
            edges[app.name] = () if spec is None else spec.depends_on
        return edges

    def start_chain(self, chain: Tuple[str, ...], deadline: float) -> bool:
        deps = chain[:-1]
        root = chain[-1]
        for dep_name in deps:
            if not self._start_named(dep_name, deadline):
                return False
            self.store.clear_scaled_to_zero(dep_name)
        return self._start_named(root, deadline)

    def load_spec(self, name: str) -> Optional[AppSpec]:
        path = AppRegistry(self.home).path_for(name)
        if not path.is_file():
            return None
        try:
            _, spec = AppDocument.load(path, expect_name=name)
        except (OSError, ValueError, OperatorError):
            return None
        return spec

    def compose_id(self, name: str) -> Optional[str]:
        for app in Stack.load_apps(self.home).apps:
            if app.name == name:
                return app.compose_id
        return None

    def _record_idle_stop_event(self, name: str, compose_id: str) -> None:
        GraphEventStore(self.home).record_scaling(
            service=compose_id,
            app=name,
            action=SCALING_ACTION_IDLE_STOP,
        )

    def _stop_scaled_chain(
        self,
        order: Tuple[str, ...],
        *,
        parent: str,
        parent_compose: str,
    ) -> None:
        for dep in order:
            compose_id = parent_compose if dep == parent else self.compose_id(dep)
            if compose_id is not None:
                self.docker.stop_service(compose_id)
            self.store.mark_scaled_to_zero(dep)

    def _start_named(self, name: str, deadline: float) -> bool:
        compose_id = self.compose_id(name)
        if compose_id is None:
            return False
        return self._ensure_running(compose_id, deadline)

    def _ensure_running(self, compose_id: str, deadline: float) -> bool:
        # Compose health is not a wake gate: start_period reports "starting", and
        # some images fail healthchecks while still serving (router_can_fetch is).
        status, _health = self.docker.service_runtime(compose_id)
        if status == "running":
            return True
        if self._clock() >= deadline:
            return False
        self.docker.start_service(compose_id)
        return self._wait_running(compose_id, deadline)

    def _wait_running(self, compose_id: str, deadline: float) -> bool:
        while self._clock() < deadline:
            status, _health = self.docker.service_runtime(compose_id)
            if status == "running":
                return True
            self._sleep(_WAKE_POLL_SECONDS)
        return False
