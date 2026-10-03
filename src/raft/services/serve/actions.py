"""Mutative service actions for ``raft serve`` (start / stop / redeploy)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from raft.errors import OperatorError

from ...adapters.docker import DockerStack
from ...adapters.shell import Shell
from ...models import App, Stack
from ...models.graph_event_store import GraphEventStore
from ...models.scaling_store import ScalingStore
from ..deploy.locking import app_and_stack_locks, stack_lock
from ..deploy.orchestrator import Orchestrator
from ..ops.logs.targets import LogsTargets


class ServeActions:
    """Start / stop / redeploy one Compose service via deploy collaborators.

    Start and stop use Compose ``up -d --no-deps`` / ``stop`` under the same
    flock locks as apply/redeploy. For apps with ``spec.scaling``, stop marks
    ``scaledToZero`` (healer skips; gate holding page) and start clears it.
    Redeploy mirrors ``raft redeploy``: apps cutover (must be running), router
    recreates, gate is refused.
    """

    def __init__(
        self,
        stack: Stack,
        *,
        orchestrator: Optional[Orchestrator] = None,
        docker: Optional[DockerStack] = None,
    ) -> None:
        self.stack = stack
        self._orch = orchestrator
        self._docker = docker
        self._targets = LogsTargets(stack)

    def start(self, name: str) -> Dict[str, Any]:
        compose_id, app = self._resolve(name)
        with self._locks(app):
            self._docker_stack().start_service(compose_id)
            if app is not None:
                self._clear_scaled_to_zero(app)
            self._record_start_event(compose_id, app)
        return self._ok("start", compose_id)

    def stop(self, name: str) -> Dict[str, Any]:
        compose_id, app = self._resolve(name)
        with self._locks(app):
            self._docker_stack().stop_service(compose_id)
            if app is not None:
                self._mark_scaled_to_zero(app)
            self._record_stop_event(compose_id, app)
        return self._ok("stop", compose_id)

    def redeploy(self, name: str) -> Dict[str, Any]:
        compose_id, app = self._resolve(name)
        orch = self._orchestrator()
        if compose_id == self.stack.gate:
            orch.redeploy("gate")
        if compose_id == self.stack.router:
            orch.redeploy_router()
            return self._ok("redeploy", compose_id)
        if compose_id == self.stack.controller:
            raise OperatorError(
                "refusing to redeploy `controller` — restart it with Start "
                "after Stop, or recreate the stack with `raft down` / `raft up`.",
                has_fix=False,
            )
        assert app is not None
        orch.redeploy_app(app.name)
        return self._ok("redeploy", compose_id)

    def _resolve(self, name: str) -> tuple[str, Optional[App]]:
        compose_id = self._targets.resolve(name)[0]
        for app in self.stack.apps:
            if app.compose_id == compose_id:
                return compose_id, app
        return compose_id, None

    def _locks(self, app: Optional[App]):
        if app is None:
            return stack_lock(self.stack.root)
        return app_and_stack_locks(self.stack.root, app.name)

    def _docker_stack(self) -> DockerStack:
        if self._docker is not None:
            return self._docker
        return DockerStack(self.stack, Shell(self.stack.root))

    def _orchestrator(self) -> Orchestrator:
        if self._orch is not None:
            return self._orch
        return Orchestrator(self.stack)

    def _clear_scaled_to_zero(self, app: App) -> None:
        store = ScalingStore(self.stack.root)
        if not store.is_scaled_to_zero(app.name):
            return
        min_up = self._min_up_seconds(app)
        store.mark_awake(app.name, min_up_seconds=min_up)

    def _mark_scaled_to_zero(self, app: App) -> None:
        if self._scaling_spec(app) is None:
            return
        ScalingStore(self.stack.root).mark_scaled_to_zero(app.name)

    def _record_stop_event(self, compose_id: str, app: Optional[App]) -> None:
        """Append a GraphEvent so Trends charts mark intentional stops."""
        GraphEventStore(self.stack.root).record_stop(
            service=compose_id,
            app=None if app is None else app.name,
        )

    def _record_start_event(self, compose_id: str, app: Optional[App]) -> None:
        """Append a GraphEvent so Trends charts mark intentional starts."""
        GraphEventStore(self.stack.root).record_start(
            service=compose_id,
            app=None if app is None else app.name,
        )

    def _min_up_seconds(self, app: App) -> float:
        scaling = self._scaling_spec(app)
        if scaling is None:
            return 60.0
        return float(scaling.min_up_seconds)

    def _scaling_spec(self, app: App):
        try:
            return self.stack.spec_for(app).scaling
        except OperatorError:
            return None

    @staticmethod
    def _ok(action: str, service: str) -> Dict[str, Any]:
        return {"ok": True, "action": action, "service": service}
