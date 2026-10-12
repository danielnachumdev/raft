"""Standalone heal poll loop (tests / legacy; product uses JobOrchestrator)."""

import logging
import time
from pathlib import Path
from typing import Callable, Optional

from ....adapters.docker import DockerStack
from ....config.settings.types import HealingConfig
from .heal import DeployFn, Healer

logger = logging.getLogger(__name__)


class HealForever:
    """Poll forever (``sleep_fn`` injectable for tests)."""

    def __init__(
        self,
        home: Path,
        config: HealingConfig,
        docker: DockerStack,
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
        deploy: Optional[DeployFn] = None,
    ) -> None:
        self._healer = Healer(home=home, config=config, docker=docker, deploy=deploy)
        self._config = config
        self._sleep = sleep_fn

    def run(self) -> None:
        self._log_startup()
        while True:
            try:
                self._healer.tick()
            except Exception:  # noqa: BLE001 — keep the controller alive
                logger.exception("heal tick failed")
            self._sleep(self._config.interval_seconds)

    def _log_startup(self) -> None:
        config = self._config
        if not config.enabled:
            logger.info(
                "healing disabled (settings healing.enabled=false); idle loop only"
            )
            return
        logger.info(
            "healing enabled interval=%ss failThreshold=%s cooldown=%ss "
            "maxRestarts=%s escalateAfterRestarts=%s",
            config.interval_seconds,
            config.fail_threshold,
            config.cooldown_seconds,
            config.max_restarts,
            config.escalate_after_restarts,
        )
