"""Phase 1 self-heal: restart unhealthy/exited apps under deploy locks."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

from raft.adapters.docker import DockerStack
from raft.config.settings_types import HealingConfig
from raft.errors import OperatorError
from raft.models.registry import AppRegistry
from raft.models.stack import Stack
from raft.services.locking import app_and_stack_locks

__all__ = ["Healer", "needs_heal", "run_heal_forever"]

logger = logging.getLogger(__name__)


def needs_heal(status: str, health: str) -> bool:
    """True when Compose indicates the app should be restarted."""
    if status in ("exited", "dead", "missing"):
        return True
    if status == "running" and health == "unhealthy":
        return True
    return False


@dataclass
class Healer:
    home: Path
    config: HealingConfig
    docker: DockerStack
    fail_counts: Dict[str, int] = field(default_factory=dict)
    restart_counts: Dict[str, int] = field(default_factory=dict)
    last_restart_at: Dict[str, float] = field(default_factory=dict)

    def tick(self, *, now: Optional[float] = None) -> None:
        if not self.config.enabled:
            logger.debug("healing disabled; skip tick")
            return
        when = time.monotonic() if now is None else now
        stack = Stack(root=self.home, apps=AppRegistry(self.home).load())
        for app in stack.apps:
            self._consider(app.name, app.compose_id, when)

    def _consider(self, name: str, compose_id: str, when: float) -> None:
        status, health = self.docker.service_runtime(compose_id)
        if self._clear_if_healthy(name, compose_id, status, health):
            return
        if not needs_heal(status, health):
            return
        fails = self.fail_counts.get(name, 0) + 1
        self.fail_counts[name] = fails
        logger.info(
            "heal observe app=%s compose=%s status=%s health=%s fails=%s/%s",
            name, compose_id, status, health, fails, self.config.fail_threshold,
        )
        if fails >= self.config.fail_threshold and not self._blocked_by_limits(name, when):
            self._restart(name, compose_id, status, when)

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

    def _blocked_by_limits(self, name: str, when: float) -> bool:
        restarts = self.restart_counts.get(name, 0)
        if restarts >= self.config.max_restarts:
            logger.warning(
                "heal give up app=%s restarts=%s (max=%s)",
                name,
                restarts,
                self.config.max_restarts,
            )
            return True
        last = self.last_restart_at.get(name)
        if last is not None and (when - last) < self.config.cooldown_seconds:
            logger.info(
                "heal cooldown app=%s remaining=%.0fs",
                name,
                self.config.cooldown_seconds - (when - last),
            )
            return True
        return False

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
        self.last_restart_at[name] = when
        logger.info(
            "heal ok app=%s restarts=%s",
            name,
            self.restart_counts[name],
        )

    def _do_restart(self, name: str, compose_id: str, status: str) -> bool:
        try:
            with app_and_stack_locks(self.home, name):
                if status in ("exited", "dead", "missing"):
                    self.docker.start_service(compose_id)
                else:
                    self.docker.restart_service(compose_id)
        except OperatorError as exc:
            logger.error("heal failed app=%s: %s", name, exc)
            return False
        return True


def run_heal_forever(
    home: Path,
    config: HealingConfig,
    docker: DockerStack,
    *,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    """Poll forever (``sleep_fn`` injectable for tests)."""
    healer = Healer(home=home, config=config, docker=docker)
    if not config.enabled:
        logger.info(
            "healing disabled (settings healing.enabled=false); idle loop only"
        )
    else:
        logger.info(
            "healing enabled interval=%ss failThreshold=%s cooldown=%ss maxRestarts=%s",
            config.interval_seconds,
            config.fail_threshold,
            config.cooldown_seconds,
            config.max_restarts,
        )
    while True:
        try:
            healer.tick()
        except Exception:  # noqa: BLE001 — keep the controller alive
            logger.exception("heal tick failed")
        sleep_fn(config.interval_seconds)
