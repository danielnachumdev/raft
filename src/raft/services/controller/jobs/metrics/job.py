"""Metrics ``ControllerJob`` — resources + HTTP edge on one schedule."""

from pathlib import Path

from raft.core.core.config.settings.types import MetricsConfig
from ...engine.job import JobIds, JobSpec, QueuePolicy
from ...engine import JobOrchestrator
from ...engine.schedule import IntervalSchedule
from ..controller_job import ControllerJob
from .http_metrics import HttpMetricsRecorder
from .metrics import MetricsRecorder


class MetricsJob(ControllerJob):
    """Wire resource + HTTP recorders as the scheduled ``metrics`` job."""

    def __init__(self, home: Path, config: MetricsConfig) -> None:
        self._config = config
        self._resources = MetricsRecorder(
            home,
            batch_size=config.batch_size,
            flush_seconds=config.flush_seconds,
            retention_max_age_days=config.retention_max_age_days,
            retention_max_bytes=config.retention_max_bytes,
        )
        self._http = HttpMetricsRecorder(
            home,
            interval_seconds=config.interval_seconds,
            batch_size=config.batch_size,
            flush_seconds=config.flush_seconds,
            retention_max_age_days=config.retention_max_age_days,
            retention_max_bytes=config.retention_max_bytes,
        )

    @property
    def job_id(self) -> str:
        return JobIds.METRICS

    def tick(self) -> None:
        self._resources.tick()
        self._http.tick()

    def attach(self, orch: JobOrchestrator) -> None:
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
