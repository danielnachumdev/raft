"""Idle stop + wake for apps with ``spec.scaling``."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from raft.adapters.docker import DockerStack
from raft.errors import OperatorError
from raft.models.app_document import AppDocument
from raft.models.manifest import AppSpec
from raft.models.registry import AppRegistry
from raft.models.scaling_spec import ScalingSpec
from raft.models.stack import Stack
from raft.services.deploy.locking import app_and_stack_locks

from .scaling_store import ScalingStore

__all__ = ["Scaler", "WAKE_HTTP_PORT"]

logger = logging.getLogger(__name__)

WAKE_HTTP_PORT = 8090
SleepFn = Callable[[float], None]


class Scaler:
    """Poll idle apps and fulfill gate wake requests under deploy locks."""

    def __init__(self, home: Path, docker: DockerStack) -> None:
        self.home = home
        self.docker = docker
        self.store = ScalingStore(home)
        self._wake_lock = threading.Lock()
        self._waking: set[str] = set()

    def tick(self, *, now: Optional[float] = None) -> None:
        when = time.time() if now is None else now
        stack = Stack(root=self.home, apps=AppRegistry(self.home).load())
        for app in stack.apps:
            spec = self._load_spec(app.name)
            if spec is None or spec.scaling is None:
                continue
            self._consider(app.name, app.compose_id, spec.scaling, when)

    def record_activity(self, name: str) -> None:
        self.store.touch_activity(name)

    def request_wake(self, name: str) -> None:
        spec = self._load_spec(name)
        if spec is None or spec.scaling is None:
            return
        self.store.request_wake(name)
        self._start_wake_thread(name, spec.scaling)

    def wake_now(self, name: str, scaling: ScalingSpec, *, now: Optional[float] = None) -> bool:
        """Start a scaled-to-zero app; returns False on failure/timeout."""
        when = time.time() if now is None else now
        state = self.store.load(name)
        if not state.scaled_to_zero:
            return True
        compose_id = self._compose_id(name)
        if compose_id is None:
            return False
        return self._do_wake(name, compose_id, scaling, when)

    def _consider(
        self, name: str, compose_id: str, scaling: ScalingSpec, when: float
    ) -> None:
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
        self._idle_stop(name, compose_id)

    def _idle_stop(self, name: str, compose_id: str) -> None:
        logger.info("scale idle-stop app=%s compose=%s", name, compose_id)
        try:
            with app_and_stack_locks(self.home, name):
                self.docker.stop_service(compose_id)
                self.store.mark_scaled_to_zero(name)
        except OperatorError as exc:
            logger.error("scale idle-stop failed app=%s: %s", name, exc)
            return
        logger.info("scale idle-stop ok app=%s", name)

    def _do_wake(
        self, name: str, compose_id: str, scaling: ScalingSpec, when: float
    ) -> bool:
        logger.info("scale wake app=%s compose=%s", name, compose_id)
        try:
            with app_and_stack_locks(self.home, name):
                self.docker.start_service(compose_id)
                self.store.mark_awake(name, min_up_seconds=scaling.min_up_seconds, now=when)
        except OperatorError as exc:
            logger.error("scale wake failed app=%s: %s", name, exc)
            return False
        logger.info("scale wake ok app=%s", name)
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
        path = AppRegistry(self.home).path_for(name)
        if not path.is_file():
            return None
        try:
            _, spec = AppDocument.load(path, expect_name=name)
        except (OSError, ValueError, OperatorError):
            return None
        return spec

    def _compose_id(self, name: str) -> Optional[str]:
        stack = Stack(root=self.home, apps=AppRegistry(self.home).load())
        for app in stack.apps:
            if app.name == name:
                return app.compose_id
        return None
