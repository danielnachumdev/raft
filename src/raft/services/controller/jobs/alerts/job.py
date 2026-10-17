"""Alerts ``ControllerJob`` — evaluate rules on an interval."""

import logging
from pathlib import Path
from typing import Optional

from raft.core.core.config.settings.alerts_config import AlertsConfig
from raft.core.observe.alerts import AlertEngine

from ...engine import JobOrchestrator
from ...engine.job import JobIds, JobSpec, QueuePolicy
from ...engine.schedule import IntervalSchedule
from ..controller_job import ControllerJob

logger = logging.getLogger(__name__)


class AlertsJob(ControllerJob):
    """Wire AlertEngine as the scheduled ``alerts`` job."""

    def __init__(
        self,
        home: Path,
        config: AlertsConfig,
        *,
        engine: Optional[AlertEngine] = None,
    ) -> None:
        self._config = config
        self._engine = engine or AlertEngine(home)

    @property
    def job_id(self) -> str:
        return JobIds.ALERTS

    def tick(self) -> None:
        try:
            self._engine.tick()
        except Exception:  # noqa: BLE001 — never stop the controller
            logger.exception("alerts tick failed")

    def attach(self, orch: JobOrchestrator) -> None:
        if not self._config.enabled:
            return
        cfg = self._config
        orch.register(
            JobSpec(
                job_id=self.job_id,
                schedule=IntervalSchedule(cfg.interval_seconds),
                timeout_seconds=cfg.timeout_seconds,
                queue_policy=QueuePolicy.SKIP_IF_RUNNING,
                run=self.tick,
            )
        )
