"""Construct ``ControllerJob``s, attach them, and run the orchestrator."""

import logging
from pathlib import Path
from typing import List, Optional

from raft.core.platform.adapters.docker import DockerStack
from raft.core.core.config.settings.types import RaftConfig
from ..jobs import (
    AcmeJobSync,
    AlertsJob,
    ControllerJob,
    HealJob,
    MetricsJob,
    ScaleJob,
    Scaler,
    ServiceLogsJob,
)
from ..engine import ClockFn, JobOrchestrator, SleepFn

logger = logging.getLogger(__name__)


class ControllerLoop:
    """Construct ``ControllerJob``s, attach them, and run the orchestrator."""

    def __init__(
        self,
        home: Path,
        config: RaftConfig,
        docker: DockerStack,
        scaler: Scaler,
    ) -> None:
        self._home = home
        self._config = config
        self._docker = docker
        self._scaler = scaler

    def run(
        self,
        *,
        sleep_fn: Optional[SleepFn] = None,
        clock: Optional[ClockFn] = None,
        orchestrator: Optional[JobOrchestrator] = None,
    ) -> None:
        orch = orchestrator or JobOrchestrator()
        for job in self._jobs(orch):
            job.attach(orch)
        self._log_startup()
        self._run_orchestrator(orch, sleep_fn=sleep_fn, clock=clock)

    def _jobs(self, orch: JobOrchestrator) -> List[ControllerJob]:
        return [
            HealJob(self._home, self._config.healing, self._docker),
            MetricsJob(self._home, self._config.metrics),
            ServiceLogsJob(self._home, self._config.service_logs, self._docker),
            AlertsJob(self._home, self._config.alerts),
            ScaleJob(self._scaler),
            AcmeJobSync(self._home, self._docker, orch),
        ]

    def _log_startup(self) -> None:
        self._log_healing()
        logger.info("scale-to-zero enabled for apps with spec.scaling")
        self._log_metrics()
        self._log_service_logs()
        self._log_alerts()

    def _log_healing(self) -> None:
        healing = self._config.healing
        if healing.enabled:
            logger.info(
                "healing enabled interval=%ss timeout=%ss failThreshold=%s",
                healing.interval_seconds,
                healing.timeout_seconds,
                healing.fail_threshold,
            )
            return
        logger.info("healing disabled; scale + idle wake loop active")

    def _log_metrics(self) -> None:
        metrics_cfg = self._config.metrics
        logger.info(
            "metrics enabled interval=%ss timeout=%ss "
            "path=state/metrics/resources.jsonl+http.jsonl",
            metrics_cfg.interval_seconds,
            metrics_cfg.timeout_seconds,
        )

    def _log_service_logs(self) -> None:
        logs_cfg = self._config.service_logs
        if logs_cfg.enabled:
            logger.info(
                "service-logs enabled interval=%ss path=services/*/logs/",
                logs_cfg.interval_seconds,
            )
            return
        logger.info("service-logs disabled")

    def _log_alerts(self) -> None:
        cfg = self._config.alerts
        if cfg.enabled:
            logger.info(
                "alerts enabled interval=%ss path=host/alerts/",
                cfg.interval_seconds,
            )
            return
        logger.info("alerts disabled")

    def _run_orchestrator(
        self,
        orch: JobOrchestrator,
        *,
        sleep_fn: Optional[SleepFn],
        clock: Optional[ClockFn],
    ) -> None:
        kwargs = {}
        if sleep_fn is not None:
            kwargs["sleep_fn"] = sleep_fn
        if clock is not None:
            kwargs["clock"] = clock
        orch.run_forever(**kwargs)
