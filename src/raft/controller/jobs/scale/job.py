"""Scale ``ControllerJob`` — idle-stop / wake via orchestrator side-tick."""

from ...orchestrator import JobOrchestrator
from ..controller_job import ControllerJob
from .scale import Scaler


class ScaleJob(ControllerJob):
    """Wire ``Scaler.tick`` as a per-cycle side-tick (not a ``JobSpec``)."""

    def __init__(self, scaler: Scaler) -> None:
        self._scaler = scaler

    @property
    def job_id(self) -> str:
        return "scale"

    def tick(self) -> None:
        self._scaler.tick()

    def attach(self, orch: JobOrchestrator) -> None:
        orch.append_side_tick(self._as_side_tick())
