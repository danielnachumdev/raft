"""Job identity, queue policy, and registration contracts for the controller."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .schedule import Schedule


class JobId(Enum):
    HEAL = "heal"
    METRICS = "metrics"
    # SCALE intentionally absent — transitional side_ticks only.


class QueuePolicy(Enum):
    SKIP_IF_RUNNING = "skipIfRunning"
    QUEUE = "queue"
    REPLACE = "replace"


@dataclass(frozen=True)
class JobSpec:
    job_id: JobId
    schedule: Schedule
    timeout_seconds: float
    queue_policy: QueuePolicy
    run: Callable[[], None]


@dataclass(frozen=True)
class JobRequest:
    """One-shot request; uses the registered JobSpec's timeout / policy / run."""

    job_id: JobId
