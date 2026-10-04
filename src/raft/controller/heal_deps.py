"""dependsOn helpers for Healer restart / escalate."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

from raft.adapters.docker import DockerStack
from raft.errors.cta import OperatorError
from raft.models.app_document import AppDocument
from raft.models.depends import AppDependsGraph, DependsOnError
from raft.models.registry import AppRegistry
from raft.models.state.scaling_store import ScalingStore
from raft.models.stack import Stack
from raft.services.deploy.locking import app_and_stack_locks

__all__ = ["HealDepends"]

logger = logging.getLogger(__name__)


class HealDepends:
    """Ensure transitive dependsOn services are running before heal actions."""

    def __init__(self, home: Path, docker: DockerStack) -> None:
        self.home = home
        self.docker = docker

    def ensure_deps_running(self, name: str) -> bool:
        deps = self.deps_before(name)
        if deps is None:
            return False
        for dep in deps:
            if not self.ensure_one_dep(dep, name):
                return False
        return True

    def deps_before(self, name: str) -> Optional[Tuple[str, ...]]:
        try:
            return AppDependsGraph(self.depends_edges()).before(name)
        except DependsOnError as exc:
            logger.error("heal dependsOn app=%s: %s", name, exc)
            return None

    def depends_edges(self) -> Dict[str, Tuple[str, ...]]:
        edges: Dict[str, Tuple[str, ...]] = {}
        for app in Stack.load_apps(self.home).apps:
            path = AppRegistry(self.home).path_for(app.name)
            edges[app.name] = self.edges_for(path, app.name)
        return edges

    def edges_for(self, path: Path, name: str) -> Tuple[str, ...]:
        if not path.is_file():
            return ()
        try:
            _, spec = AppDocument.load(path, expect_name=name)
        except (OSError, ValueError, OperatorError):
            return ()
        return spec.depend_names()

    def ensure_one_dep(self, dep: str, for_app: str) -> bool:
        if ScalingStore(self.home).is_scaled_to_zero(dep):
            logger.info("heal defer app=%s dep=%s scaled-to-zero", for_app, dep)
            return False
        compose_id = self.compose_id(dep)
        if compose_id is None:
            return False
        status, _health = self.docker.service_runtime(compose_id)
        if status == "running":
            return True
        return self.start_dep(dep, compose_id)

    def start_dep(self, dep: str, compose_id: str) -> bool:
        logger.info("heal start dep=%s compose=%s", dep, compose_id)
        try:
            with app_and_stack_locks(self.home, dep):
                self.docker.start_service(compose_id)
        except OperatorError as exc:
            logger.error("heal start dep failed dep=%s: %s", dep, exc)
            return False
        return True

    def compose_id(self, name: str) -> Optional[str]:
        for app in Stack.load_apps(self.home).apps:
            if app.name == name:
                return app.compose_id
        return None
