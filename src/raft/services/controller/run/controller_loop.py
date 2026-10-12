"""Construct ``ControllerJob``s, attach them, and run the orchestrator."""

import logging
from pathlib import Path
from typing import List, Optional

from raft.core.platform.adapters.docker import DockerStack
from raft.core.core.config.settings.types import RaftConfig
from ..jobs import (
    AcmeJobSync,
    ControllerJob,
    HealJob,
    MetricsJob,
    ScaleJob,
    Scaler,
)
from ..orchestrator import ClockFn, JobOrchestrator, SleepFn

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
            ScaleJob(self._scaler),
            AcmeJobSync(self._home, self._docker, orch),
        ]

    def _log_startup(self) -> None:
        healing = self._config.healing
        metrics_cfg = self._config.metrics
        if healing.enabled:
            logger.info(
                "healing enabled interval=%ss timeout=%ss failThreshold=%s",
                healing.interval_seconds,
                healing.timeout_seconds,
                healing.fail_threshold,
            )
        else:
            logger.info("healing disabled; scale + idle wake loop active")
        logger.info("scale-to-zero enabled for apps with spec.scaling")
        logger.info(
            "metrics enabled interval=%ss timeout=%ss "
            "path=state/metrics/resources.jsonl+http.jsonl",
            metrics_cfg.interval_seconds,
            metrics_cfg.timeout_seconds,
        )

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
