"""Mutative per-service actions (start / stop / redeploy / purge)."""

from typing import Any, Dict, Optional, Tuple

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.app import App
from raft.core.core.models.stack import Stack
from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from raft.core.observe.ops.actions.start_depends import StartDepends
from raft.core.observe.ops.logs.targets import LogsTargets
from raft.core.observe.ops.purge import Purge
from raft.core.platform.adapters.docker import DockerStack
from raft.core.platform.adapters.shell import Shell
from raft.core.platform.locking import AppAndStackLocks, AppsAndStackLocks, StackLock


class ServiceActions:
    """Start / stop / redeploy one Compose service via deploy collaborators.

    Start and stop use Compose ``up -d --no-deps`` / ``stop`` under the same
    flock locks as apply/redeploy. Default start also brings up transitive
    ``spec.dependsOn`` first (wake order); pass ``no_deps=True`` to skip.
    For apps with ``spec.scaling``, stop marks ``scaledToZero`` (healer skips;
    gate holding page) and start clears it. Redeploy mirrors ``raft
    redeploy``: apps cutover (must be running), router recreates, dashboard
    rebuilds when ``dashboard.enabled``, gate and controller are refused.
    ``purge`` removes unused Docker images/cache.
    """

    def __init__(
        self,
        stack: Stack,
        *,
        orchestrator: Optional[Orchestrator] = None,
        docker: Optional[DockerStack] = None,
        purge: Optional[Purge] = None,
    ) -> None:
        self.stack = stack
        self._orch = orchestrator
        self._docker = docker
        self._purge = purge
        self._targets = LogsTargets(stack)

    def bind_stack(self, stack: Stack) -> None:
        """Point at a reloaded Stack after serve registry refresh."""
        self.stack = stack
        self._targets.stack = stack
        self._orch = None
        self._purge = None
        if self._docker is not None:
            self._docker.stack = stack

    def purge(self) -> Dict[str, Any]:
        """Purge unused Docker images/build cache; same path as ``raft purge``."""
        return self._purge_svc().execute().as_api()

    def start(self, name: str, *, no_deps: bool = False) -> Dict[str, Any]:
        compose_id, app = self._resolve(name)
        if app is None or no_deps:
            return self._start_one(compose_id, app, no_deps=no_deps, started_deps=())
        deps_helper = StartDepends(self.stack, self._docker_stack())
        chain = deps_helper.wake_chain(app.name)
        if len(chain) <= 1:
            return self._start_one(compose_id, app, no_deps=False, started_deps=())
        return self._start_with_deps(compose_id, app, deps_helper, chain)

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
        if compose_id == self.stack.dashboard:
            self._redeploy_dashboard(orch)
            return self._ok("redeploy", compose_id)
        self._refuse_controller_redeploy(compose_id)
        assert app is not None
        orch.redeploy_app(app.name)
        return self._ok("redeploy", compose_id)

    def _redeploy_dashboard(self, orch: Orchestrator) -> None:
        if self.stack.dashboard not in self.stack.control_plane_services:
            raise OperatorError(
                "refusing to redeploy `dashboard` while dashboard.enabled "
                "is false.\n"
                "Fix: enable the dashboard in Settings "
                "(dashboard.enabled: true), run `raft render`, then "
                "`raft start dashboard` or `raft redeploy dashboard`.",
                has_fix=False,
            )
        orch.redeploy_dashboard()

    def _start_with_deps(
        self,
        compose_id: str,
        app: App,
        deps_helper: StartDepends,
        chain: Tuple[str, ...],
    ) -> Dict[str, Any]:
        with AppsAndStackLocks(self.stack.root, chain):
            started = self._start_dep_names(deps_helper, chain[:-1])
            self._docker_stack().start_service(compose_id)
            self._clear_scaled_to_zero(app)
            deps_helper.restore_upstreams(chain)
            self._record_start_event(compose_id, app)
        return self._ok("start", compose_id, no_deps=False, started_deps=started)

    def _start_one(
        self,
        compose_id: str,
        app: Optional[App],
        *,
        no_deps: bool,
        started_deps: Tuple[str, ...],
    ) -> Dict[str, Any]:
        with self._locks(app):
            self._docker_stack().start_service(compose_id)
            if app is not None:
                self._clear_scaled_to_zero(app)
            self._record_start_event(compose_id, app)
        return self._ok(
            "start", compose_id, no_deps=no_deps, started_deps=started_deps
        )

    def _start_dep_names(
        self, deps_helper: StartDepends, dep_names: Tuple[str, ...]
    ) -> Tuple[str, ...]:
        started: list[str] = []
        for dep_name in dep_names:
            deps_helper.start_dep(dep_name)
            started.append(dep_name)
        return tuple(started)

    def _refuse_controller_redeploy(self, compose_id: str) -> None:
        if compose_id != self.stack.controller:
            return
        raise OperatorError(
            "refusing to redeploy `controller` — restart it with Start "
            "after Stop, or recreate the stack with `raft down` / `raft up`.",
            has_fix=False,
        )

    def _resolve(self, name: str) -> tuple[str, Optional[App]]:
        compose_id = self._targets.resolve(name)[0]
        for app in self.stack.apps:
            if app.compose_id == compose_id:
                return compose_id, app
        return compose_id, None

    def _locks(self, app: Optional[App]):
        if app is None:
            return StackLock(self.stack.root)
        return AppAndStackLocks(self.stack.root, app.name)

    def _docker_stack(self) -> DockerStack:
        if self._docker is not None:
            return self._docker
        return DockerStack(self.stack, Shell(self.stack.root))

    def _orchestrator(self) -> Orchestrator:
        if self._orch is not None:
            return self._orch
        return Orchestrator(self.stack)

    def _purge_svc(self) -> Purge:
        if self._purge is not None:
            return self._purge
        return Purge(self.stack)

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
    def _ok(
        action: str,
        service: str,
        *,
        no_deps: bool = False,
        started_deps: Tuple[str, ...] = (),
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"ok": True, "action": action, "service": service}
        if action == "start":
            payload["no_deps"] = no_deps
            payload["started_deps"] = list(started_deps)
        return payload
