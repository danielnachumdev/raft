"""``ControllerJob`` ABC — uniform attach surface for the controller loop."""

import logging
from abc import ABC, abstractmethod
from typing import Callable

from ..engine import JobOrchestrator

logger = logging.getLogger(__name__)

SideTick = Callable[[], None]


class ControllerJob(ABC):
    """One controller concern: identity, work unit, and orchestrator wiring."""

    @property
    @abstractmethod
    def job_id(self) -> str:
        """Stable identity for logs and (when scheduled) ``JobSpec.job_id``."""

    @abstractmethod
    def tick(self) -> None:
        """One unit of work (scheduled ``JobSpec.run`` or side-tick body)."""

    @abstractmethod
    def attach(self, orch: JobOrchestrator) -> None:
        """Register a ``JobSpec`` and/or append a side-tick on ``orch``."""

    def _as_side_tick(self) -> SideTick:
        """Wrap ``tick`` so a failing side-tick cannot kill the loop."""
        label = self.job_id

        def wrapped() -> None:
            try:
                self.tick()
            except Exception:  # noqa: BLE001 — keep the controller alive
                logger.exception("%s tick failed", label)

        return wrapped
