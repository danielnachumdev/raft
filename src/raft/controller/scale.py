"""Idle stop + wake for apps with ``spec.scaling``."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from raft.adapters.docker import DockerStack
from raft.controller.scale_depends import ScaleDepends
from raft.controller.scale_wake import ScaleWake
from raft.models.manifest import AppSpec
from raft.models.scaling_spec import ScalingSpec
from raft.models.state.scaling_store import ScalingStore
from raft.models.stack import Stack
from raft.notify.control_events import ControlPlaneEvents
from raft.notify.notifier import Notifier

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
        notifier: Optional[Notifier] = None,
    ) -> None:
        self.home = home
        self.docker = docker
        self._clock = clock
        self._sleep = sleep
        self._notifier = notifier if notifier is not None else Notifier(home)
        self.store = ScalingStore(home)
        self._bind_collaborators()
        self._wake_lock = threading.Lock()
        self._waking: set[str] = set()

    def _bind_collaborators(self) -> None:
        # Lambdas so unit tests can replace ``_clock`` / ``_sleep`` after init.
        self._deps = ScaleDepends(
            self.home,
            self.docker,
            self.store,
            clock=lambda: self._clock(),
            sleep=lambda s: self._sleep(s),
        )
        self._wake = ScaleWake(
            self.home,
            self.docker,
            self.store,
            self._deps,
            clock=lambda: self._clock(),
            sleep=lambda s: self._sleep(s),
        )

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
        wake_id = self.store.request_wake(name)
        if wake_id:
            logger.info("scale wake request app=%s id=%s", name, wake_id)
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
        return self._wake.do_wake(name, scaling, when)

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
            detail = self.store.wake_progress_log(name)
            logger.warning(
                "scale wake timeout app=%s id=%s after %.0fs %s",
                name,
                state.wake_id or "-",
                scaling.wake_timeout_seconds,
                detail,
            )
            self.store.mark_wake_timeout(name)
            self._notify_wake_timeout(name, state.wake_id or "", scaling, detail)
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

    def _notify_wake_timeout(
        self,
        name: str,
        wake_id: str,
        scaling: ScalingSpec,
        detail: str,
    ) -> None:
        self._notifier.notify(
            ControlPlaneEvents.scale_wake_timeout(
                name,
                wake_id=wake_id,
                timeout_seconds=scaling.wake_timeout_seconds,
                detail=detail,
            )
        )

    def _load_spec(self, name: str) -> Optional[AppSpec]:
        return self._deps.load_spec(name)

    def _compose_id(self, name: str) -> Optional[str]:
        return self._deps.compose_id(name)
