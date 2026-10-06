"""Job identity, queue policy, and registration contracts for the controller."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Union

from .schedule import Schedule


class JobId(Enum):
    HEAL = "heal"
    METRICS = "metrics"
    # SCALE intentionally absent — transitional side_ticks only.


# Fixed singletons (heal/metrics) plus dynamic string ids (e.g. ``acme:<app>``).
JobKey = Union[JobId, str]


class QueuePolicy(Enum):
    SKIP_IF_RUNNING = "skipIfRunning"
    QUEUE = "queue"
    REPLACE = "replace"


@dataclass(frozen=True)
class JobSpec:
    job_id: JobKey
    schedule: Schedule
    timeout_seconds: float
    queue_policy: QueuePolicy
    run: Callable[[], None]


@dataclass(frozen=True)
class JobRequest:
    """One-shot request; uses the registered JobSpec's timeout / policy / run."""

    job_id: JobKey


class JobKeys:
    """Normalize JobKey for logs / thread names."""

    @staticmethod
    def label(job_id: JobKey) -> str:
        return job_id.value if isinstance(job_id, JobId) else job_id
