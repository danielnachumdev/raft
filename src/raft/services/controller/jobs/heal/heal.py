"""Self-heal: Compose restart/start, then escalate to raft redeploy/cutover."""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

from raft.core.platform.adapters.docker import DockerStack
from raft.core.core.config.settings.types import HealingConfig
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from raft.core.core.errors.cta import OperatorError
from raft.core.platform.locking import AppAndStackLocks
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.core.models.stack import Stack
from raft.core.observe.notify.control_events import ControlPlaneEvents
from raft.core.observe.notify.notifier import Notifier
from .deps import HealDepends

__all__ = ["Healer"]

logger = logging.getLogger(__name__)

DeployFn = Callable[[str], None]
NeedsHealFn = Callable[[], None]


@dataclass
class Healer:
    home: Path
    config: HealingConfig
    docker: DockerStack
    deploy: Optional[DeployFn] = None
    on_needs_heal: Optional[NeedsHealFn] = None
    notifier: Optional[Notifier] = None
    fail_counts: Dict[str, int] = field(default_factory=dict)
    restart_counts: Dict[str, int] = field(default_factory=dict)
    escalate_counts: Dict[str, int] = field(default_factory=dict)
    last_act_at: Dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._deps = HealDepends(self.home, self.docker)
        if self.notifier is None:
            self.notifier = Notifier(self.home)

    @staticmethod
    def needs_heal(status: str, health: str) -> bool:
        """True when Compose indicates the app should be healed."""
        if status in ("exited", "dead", "missing"):
            return True
        if status == "running" and health == "unhealthy":
            return True
        return False

    def tick(self, *, now: Optional[float] = None) -> None:
        if not self.config.enabled:
            logger.debug("healing disabled; skip tick")
            return
        when = time.monotonic() if now is None else now
        stack = Stack.load_apps(self.home)
        observed = False
        for app in stack.apps:
            if self._consider(app.name, app.compose_id, when):
                observed = True
        if observed:
            self._nudge_metrics()

    def _nudge_metrics(self) -> None:
        if self.on_needs_heal is None:
            return
        self.on_needs_heal()

    def _consider(self, name: str, compose_id: str, when: float) -> bool:
        if ScalingStore(self.home).is_scaled_to_zero(name):
            logger.debug("heal skip scaled-to-zero app=%s", name)
            self.fail_counts.pop(name, None)
            return False
        status, health = self.docker.service_runtime(compose_id)
        if self._clear_if_healthy(name, compose_id, status, health):
            return False
        if not self.needs_heal(status, health):
            return False
        self._record_fail_and_act(name, compose_id, status, health, when)
        return True

    def _record_fail_and_act(
        self, name: str, compose_id: str, status: str, health: str, when: float
    ) -> None:
        fails = self.fail_counts.get(name, 0) + 1
        self.fail_counts[name] = fails
        logger.info(
            "heal observe app=%s compose=%s status=%s health=%s fails=%s/%s",
            name,
            compose_id,
            status,
            health,
            fails,
            self.config.fail_threshold,
        )
        if fails >= self.config.fail_threshold:
            self._heal_action(name, compose_id, status, when)

    def _clear_if_healthy(
        self, name: str, compose_id: str, status: str, health: str
    ) -> bool:
        if not (status == "running" and health in ("healthy", "none", "starting")):
            return False
        if self.fail_counts.pop(name, None):
            logger.info(
                "heal clear app=%s compose=%s status=%s health=%s",
                name,
                compose_id,
                status,
                health,
            )
        return True

    def _heal_action(self, name: str, compose_id: str, status: str, when: float) -> None:
        if self._cooldown_blocks(name, when):
            return
        if self.escalate_counts.get(name, 0) >= 1:
            logger.warning("heal give up app=%s after escalate", name)
            return
        if self._ready_to_escalate(name):
            self._escalate(name, compose_id, when)
            return
        self._restart(name, compose_id, status, when)

    def _cooldown_blocks(self, name: str, when: float) -> bool:
        last = self.last_act_at.get(name)
        if last is None or (when - last) >= self.config.cooldown_seconds:
            return False
        logger.info(
            "heal cooldown app=%s remaining=%.0fs",
            name,
            self.config.cooldown_seconds - (when - last),
        )
        return True

    def _ready_to_escalate(self, name: str) -> bool:
        restarts = self.restart_counts.get(name, 0)
        return (
            restarts >= self.config.escalate_after_restarts
            or restarts >= self.config.max_restarts
        )

    def _restart(self, name: str, compose_id: str, status: str, when: float) -> None:
        logger.info(
            "heal act app=%s compose=%s action=restart status=%s",
            name,
            compose_id,
            status,
        )
        if not self._do_restart(name, compose_id, status):
            return
        self.fail_counts[name] = 0
        self.restart_counts[name] = self.restart_counts.get(name, 0) + 1
        self.last_act_at[name] = when
        logger.info(
            "heal ok app=%s restarts=%s",
            name,
            self.restart_counts[name],
        )

    def _do_restart(self, name: str, compose_id: str, status: str) -> bool:
        if not self._deps.ensure_deps_running(name):
            return False
        try:
            with AppAndStackLocks(self.home, name):
                if status in ("exited", "dead", "missing"):
                    self.docker.start_service(compose_id)
                else:
                    self.docker.restart_service(compose_id)
        except OperatorError as exc:
            logger.error("heal failed app=%s: %s", name, exc)
            return False
        return True

    def _escalate(self, name: str, compose_id: str, when: float) -> None:
        restarts = self.restart_counts.get(name, 0)
        logger.info(
            "heal escalate app=%s compose=%s restarts=%s",
            name,
            compose_id,
            restarts,
        )
        self._notify_escalate(name, compose_id, restarts)
        logger.info("heal redeploy app=%s", name)
        if not self._do_escalate(name):
            return
        self.fail_counts[name] = 0
        self.escalate_counts[name] = self.escalate_counts.get(name, 0) + 1
        self.last_act_at[name] = when
        logger.info("heal redeploy ok app=%s", name)

    def _notify_escalate(self, name: str, compose_id: str, restarts: int) -> None:
        assert self.notifier is not None
        self.notifier.notify(
            ControlPlaneEvents.heal_escalate(
                name, compose_id=compose_id, restarts=restarts
            )
        )

    def _do_escalate(self, name: str) -> bool:
        if not self._deps.ensure_deps_running(name):
            return False
        try:
            self._deploy_app(name)
        except OperatorError as exc:
            logger.error("heal redeploy failed app=%s: %s", name, exc)
            return False
        return True

    def _deploy_app(self, name: str) -> None:
        if self.deploy is not None:
            self.deploy(name)
            return
        Orchestrator(Stack.load_apps(self.home)).ensure_app_deployed(name)
