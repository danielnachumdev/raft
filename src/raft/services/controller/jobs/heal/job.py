"""Heal ``ControllerJob`` — registers the periodic heal ``JobSpec``."""

from pathlib import Path

from raft.core.platform.adapters.docker import DockerStack
from raft.core.core.config.settings.types import HealingConfig
from ...engine.job import JobIds, JobRequest, JobSpec, QueuePolicy
from ...engine import JobOrchestrator
from ...engine.schedule import IntervalSchedule
from ..controller_job import ControllerJob
from .heal import Healer


class HealJob(ControllerJob):
    """Wire ``Healer.tick`` as the scheduled ``heal`` job."""

    def __init__(
        self,
        home: Path,
        config: HealingConfig,
        docker: DockerStack,
    ) -> None:
        self._healer = Healer(home=home, config=config, docker=docker)

    @property
    def job_id(self) -> str:
        return JobIds.HEAL

    def tick(self) -> None:
        self._healer.tick()

    def attach(self, orch: JobOrchestrator) -> None:
        self._healer.on_needs_heal = self._nudge_metrics(orch)
        orch.register(self._spec())

    def _spec(self) -> JobSpec:
        cfg = self._healer.config
        return JobSpec(
            job_id=self.job_id,
            schedule=IntervalSchedule(cfg.interval_seconds),
            timeout_seconds=cfg.timeout_seconds,
            queue_policy=QueuePolicy.SKIP_IF_RUNNING,
            run=self.tick,
        )

    @staticmethod
    def _nudge_metrics(orch: JobOrchestrator):
        def nudge() -> None:
            orch.enqueue(JobRequest(job_id=JobIds.METRICS))

        return nudge
