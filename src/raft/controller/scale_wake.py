"""Wake execution + reachability waits for Scaler."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional, Tuple

from raft.adapters.docker import DockerStack
from raft.controller.scale_depends import ScaleDepends
from raft.errors.cta import OperatorError
from raft.models.manifest import AppSpec
from raft.models.scaling_spec import ScalingSpec
from raft.models.state.graph_event_kinds import SCALING_ACTION_WAKE
from raft.models.state.graph_event_store import GraphEventStore
from raft.models.state.scaling_store import ScalingStore
from raft.models.stack import Stack
from raft.locking.locking import apps_and_stack_locks

__all__ = ["ScaleWake"]

logger = logging.getLogger(__name__)

SleepFn = Callable[[float], None]
_WAKE_POLL_SECONDS = 0.2


class ScaleWake:
    """Start a scaled-to-zero chain and wait until Host routing is live."""

    def __init__(
        self,
        home: Path,
        docker: DockerStack,
        store: ScalingStore,
        deps: ScaleDepends,
        *,
        clock: Callable[[], float],
        sleep: SleepFn,
    ) -> None:
        self.home = home
        self.docker = docker
        self.store = store
        self._deps = deps
        self._clock = clock
        self._sleep = sleep

    def do_wake(self, name: str, scaling: ScalingSpec, when: float) -> bool:
        chain = self._deps.wake_chain(name)
        if chain is None:
            return False
        deadline = self._clock() + scaling.wake_timeout_seconds
        diag = self._diag_id(name)
        logger.info("scale wake app=%s id=%s chain=%s", name, diag, ",".join(chain))
        try:
            with apps_and_stack_locks(self.home, chain):
                ok = self.wake_under_lock(name, chain, scaling, when, deadline)
        except OperatorError as exc:
            logger.error("scale wake failed app=%s id=%s: %s", name, diag, exc)
            return False
        return self._log_wake_outcome(name, diag, ok)

    def _log_wake_outcome(self, name: str, diag: str, ok: bool) -> bool:
        if ok:
            logger.info("scale wake ok app=%s id=%s", name, diag)
        else:
            logger.error(
                "scale wake incomplete app=%s id=%s %s",
                name,
                diag,
                self.store.wake_progress_log(name),
            )
        return ok

    def wake_under_lock(
        self,
        name: str,
        chain: Tuple[str, ...],
        scaling: ScalingSpec,
        when: float,
        deadline: float,
    ) -> bool:
        if not self._deps.start_chain(chain, deadline):
            return False
        # Direct Docker DNS fetch proves listen; Host via router proves nginx
        # re-resolved the upstream IP (static resolve at reload). Holding stays
        # until Host works so visitors never see a cleared marker + 502.
        if not self.wait_app_reachable(name, deadline):
            self.store.note_wake_progress(name, "wait_fetch", service=name)
            return False
        if not self.wait_nginx_host(name, deadline):
            self.store.note_wake_progress(name, "wait_host", service=name)
            return False
        self.store.mark_awake(name, min_up_seconds=scaling.min_up_seconds, now=when)
        self.record_wake_event(name)
        return True

    def record_wake_event(self, name: str) -> None:
        compose_id = self._deps.compose_id(name)
        if compose_id is None:
            return
        try:
            GraphEventStore(self.home).record_scaling(
                service=compose_id,
                app=name,
                action=SCALING_ACTION_WAKE,
            )
        except OSError:
            # Wake must still succeed if events FS is RO (stale controller mounts).
            logger.warning(
                "graph event wake record failed app=%s", name, exc_info=True
            )

    def wait_app_reachable(self, name: str, deadline: float) -> bool:
        """Poll until the router network can reach the app container."""
        targets = self.http_fetch_targets(name)
        if not targets:
            return True
        while self._clock() < deadline:
            if self.router_reaches(targets):
                return True
            self._sleep(_WAKE_POLL_SECONDS)
        return False

    def wait_nginx_host(self, name: str, deadline: float) -> bool:
        """Reload router nginx until Host routing hits the woken upstream."""
        target = self.host_fetch_target(name)
        while self._clock() < deadline:
            self.docker.reload_router_nginx()
            if target is None or self.docker.router_serves_host(target[0], path=target[1]):
                return True
            self._sleep(_WAKE_POLL_SECONDS)
        return False

    def http_fetch_targets(self, name: str) -> Tuple[Tuple[str, int, str], ...]:
        compose_id = self._deps.compose_id(name)
        spec = self._load_spec(name)
        if compose_id is None or spec is None:
            return ()
        path = "/" if spec.readiness is None else spec.readiness.path
        return tuple((compose_id, p.container_port, path) for p in spec.http_ports())

    def host_fetch_target(self, name: str) -> Optional[Tuple[str, str]]:
        public_host = self.public_host(name)
        spec = self._load_spec(name)
        if not public_host or spec is None:
            return None
        path = "/" if spec.readiness is None else spec.readiness.path
        return (public_host, path)

    def public_host(self, name: str) -> Optional[str]:
        for app in Stack.load_apps(self.home).apps:
            if app.name == name and app.public_host:
                return app.public_host
        return None

    def router_reaches(self, targets: Tuple[Tuple[str, int, str], ...]) -> bool:
        for host, port, path in targets:
            if not self.docker.router_can_fetch(host, port=port, path=path):
                return False
        return True

    def _diag_id(self, name: str) -> str:
        return self.store.load(name).wake_id or "-"

    def _load_spec(self, name: str) -> Optional[AppSpec]:
        return self._deps.load_spec(name)
