"""Service-logs ``ControllerJob`` — continuous Docker → retained store."""

from pathlib import Path

from raft.core.core.config.settings.types import ServiceLogsConfig
from raft.core.platform.adapters.docker.stack import DockerStack
from ...engine.job import JobIds, JobSpec, QueuePolicy
from ...engine import JobOrchestrator
from ...engine.schedule import IntervalSchedule
from ..controller_job import ControllerJob
from .shipper import ServiceLogsShipper


class ServiceLogsJob(ControllerJob):
    """Wire :class:`ServiceLogsShipper` on the ``service-logs`` schedule."""

    def __init__(
        self,
        home: Path,
        config: ServiceLogsConfig,
        docker: DockerStack,
    ) -> None:
        self._config = config
        self._shipper = ServiceLogsShipper(home, config, docker)

    @property
    def job_id(self) -> str:
        return JobIds.SERVICE_LOGS

    def tick(self) -> None:
        self._shipper.tick()

    def attach(self, orch: JobOrchestrator) -> None:
        cfg = self._config
        if not cfg.enabled:
            return
        orch.register(
            JobSpec(
                job_id=self.job_id,
                schedule=IntervalSchedule(cfg.interval_seconds),
                timeout_seconds=cfg.timeout_seconds,
                queue_policy=QueuePolicy.SKIP_IF_RUNNING,
                run=self.tick,
            )
        )
