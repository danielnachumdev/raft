"""Idle stop + wake for apps with ``spec.scaling``."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Tuple

from raft.adapters.docker import DockerStack
from raft.controller.scale_depends import ScaleDepends
from raft.errors import OperatorError
from raft.models.manifest import AppSpec
from raft.models.scaling_spec import ScalingSpec
from raft.models.scaling_store import ScalingStore
from raft.models.stack import Stack
from raft.services.deploy.locking import apps_and_stack_locks

__all__ = ["Scaler", "WAKE_HTTP_PORT"]

logger = logging.getLogger(__name__)

WAKE_HTTP_PORT = 8090
SleepFn = Callable[[float], None]
_WAKE_POLL_SECONDS = 0.2


class Scaler:
    """Poll idle apps and fulfill gate wake requests under deploy locks."""

    def __init__(
        self,
        home: Path,
        docker: DockerStack,
        *,
        clock: Callable[[], float] = time.time,
        sleep: SleepFn = time.sleep,
    ) -> None:
        self.home = home
        self.docker = docker
        self._clock = clock
        self._sleep = sleep
        self.store = ScalingStore(home)
        # Lambdas so unit tests can replace ``_clock`` / ``_sleep`` after init.
        self._deps = ScaleDepends(
            home,
            docker,
            self.store,
            clock=lambda: self._clock(),
            sleep=lambda s: self._sleep(s),
        )
        self._wake_lock = threading.Lock()
        self._waking: set[str] = set()

    def tick(self, *, now: Optional[float] = None) -> None:
        when = time.time() if now is None else now
        for app in Stack.load_apps(self.home).apps:
            spec = self._load_spec(app.name)
            if spec is None or spec.scaling is None:
                continue
            self._consider(app.name, app.compose_id, spec.scaling, when)

    def record_activity(self, name: str) -> None:
        self.store.touch_activity(name, now=self._clock())

    def idle_stop_now(self, name: str) -> None:
        """Stop a running scaled app (and co-stop deps) as if idle elapsed."""
        compose_id = self._compose_id(name)
        if compose_id is None:
            return
        self._deps.idle_stop(name, compose_id)

    def request_wake(self, name: str) -> None:
        spec = self._load_spec(name)
        if spec is None or spec.scaling is None:
            return
        self.store.request_wake(name)
        self._start_wake_thread(name, spec.scaling)

    def wake_now(self, name: str, scaling: ScalingSpec, *, now: Optional[float] = None) -> bool:
        """Start a scaled-to-zero app (and dependsOn); False on failure/timeout.

        If the store already says awake but the Compose chain is down (e.g. a
        prior wake cleared markers then containers vanished), still start them.
        """
        when = time.time() if now is None else now
        if self._compose_id(name) is None:
            return False
        if not self.store.load(name).scaled_to_zero and self._chain_running(name):
            return True
        return self._do_wake(name, scaling, when)

    def _chain_running(self, name: str) -> bool:
        chain = self._deps.wake_chain(name)
        if chain is None:
            return False
        for dep in chain:
            compose_id = self._compose_id(dep)
            if compose_id is None:
                return False
            status, _health = self.docker.service_runtime(compose_id)
            if status != "running":
                return False
        return True

    def wait_wake_idle(self, *, timeout: float = 60.0) -> None:
        """Block until no wake worker is in-flight for this scaler (tests / sync)."""
        deadline = self._clock() + timeout
        while self._clock() < deadline:
            with self._wake_lock:
                if not self._waking:
                    return
            self._sleep(_WAKE_POLL_SECONDS)
        raise TimeoutError("wake worker still running")

    def _consider(self, name: str, compose_id: str, scaling: ScalingSpec, when: float) -> None:
        state = self.store.load(name)
        if state.scaled_to_zero:
            self._consider_scaled(name, compose_id, scaling, state, when)
            return
        self._consider_idle(name, compose_id, scaling, state, when)

    def _consider_scaled(
        self, name: str, compose_id: str, scaling: ScalingSpec, state, when: float
    ) -> None:
        if state.wake_requested_at is None:
            return
        elapsed = when - state.wake_requested_at
        if elapsed >= scaling.wake_timeout_seconds and not state.wake_timed_out:
            logger.warning(
                "scale wake timeout app=%s after %.0fs",
                name,
                scaling.wake_timeout_seconds,
            )
            self.store.mark_wake_timeout(name)
            return
        if state.wake_timed_out:
            return
        self._start_wake_thread(name, scaling)

    def _consider_idle(
        self, name: str, compose_id: str, scaling: ScalingSpec, state, when: float
    ) -> None:
        status, _health = self.docker.service_runtime(compose_id)
        if status != "running":
            return
        last = state.last_activity_at
        if last is None:
            self.store.touch_activity(name, now=when)
            return
        if state.min_up_until is not None and when < state.min_up_until:
            return
        if (when - last) < scaling.idle_seconds:
            return
        self._deps.idle_stop(name, compose_id)

    def _do_wake(self, name: str, scaling: ScalingSpec, when: float) -> bool:
        chain = self._deps.wake_chain(name)
        if chain is None:
            return False
        deadline = self._clock() + scaling.wake_timeout_seconds
        logger.info("scale wake app=%s chain=%s", name, ",".join(chain))
        try:
            with apps_and_stack_locks(self.home, chain):
                ok = self._wake_under_lock(name, chain, scaling, when, deadline)
        except OperatorError as exc:
            logger.error("scale wake failed app=%s: %s", name, exc)
            return False
        if ok:
            logger.info("scale wake ok app=%s", name)
        else:
            logger.error("scale wake incomplete app=%s", name)
        return ok

    def _wake_under_lock(
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
        if not self._wait_app_reachable(name, deadline):
            return False
        if not self._wait_nginx_host(name, deadline):
            return False
        self.store.mark_awake(name, min_up_seconds=scaling.min_up_seconds, now=when)
        return True

    def _wait_app_reachable(self, name: str, deadline: float) -> bool:
        """Poll until the router network can reach the app container."""
        targets = self._http_fetch_targets(name)
        if not targets:
            return True
        while self._clock() < deadline:
            if self._router_reaches(targets):
                return True
            self._sleep(_WAKE_POLL_SECONDS)
        return False

    def _wait_nginx_host(self, name: str, deadline: float) -> bool:
        """Reload router nginx until Host routing hits the woken upstream."""
        target = self._host_fetch_target(name)
        while self._clock() < deadline:
            self.docker.reload_router_nginx()
            if target is None or self.docker.router_serves_host(target[0], path=target[1]):
                return True
            self._sleep(_WAKE_POLL_SECONDS)
        return False

    def _http_fetch_targets(self, name: str) -> Tuple[Tuple[str, int, str], ...]:
        compose_id = self._compose_id(name)
        spec = self._load_spec(name)
        if compose_id is None or spec is None:
            return ()
        path = "/" if spec.readiness is None else spec.readiness.path
        return tuple((compose_id, p.container_port, path) for p in spec.http_ports())

    def _host_fetch_target(self, name: str) -> Optional[Tuple[str, str]]:
        public_host = self._public_host(name)
        spec = self._load_spec(name)
        if not public_host or spec is None:
            return None
        path = "/" if spec.readiness is None else spec.readiness.path
        return (public_host, path)

    def _public_host(self, name: str) -> Optional[str]:
        for app in Stack.load_apps(self.home).apps:
            if app.name == name and app.public_host:
                return app.public_host
        return None

    def _router_reaches(self, targets: Tuple[Tuple[str, int, str], ...]) -> bool:
        for host, port, path in targets:
            if not self.docker.router_can_fetch(host, port=port, path=path):
                return False
        return True

    def _start_wake_thread(self, name: str, scaling: ScalingSpec) -> None:
        with self._wake_lock:
            if name in self._waking:
                return
            self._waking.add(name)
        thread = threading.Thread(
            target=self._wake_worker,
            args=(name, scaling),
            name=f"raft-wake-{name}",
            daemon=True,
        )
        thread.start()

    def _wake_worker(self, name: str, scaling: ScalingSpec) -> None:
        try:
            self.wake_now(name, scaling)
        finally:
            with self._wake_lock:
                self._waking.discard(name)

    def _load_spec(self, name: str) -> Optional[AppSpec]:
        return self._deps.load_spec(name)

    def _compose_id(self, name: str) -> Optional[str]:
        return self._deps.compose_id(name)
