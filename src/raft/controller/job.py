"""Job identity, queue policy, and registration contracts for the controller."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from .schedule import Schedule


class JobType(Enum):
    """Kind of controller work (not the orchestrator key)."""

    HEAL = "heal"
    METRICS = "metrics"
    ACME = "acme"
    # SCALE intentionally absent — transitional side_ticks only.


class JobIds:
    """Stable string orchestrator keys: ``{type}`` or ``{type}:{subject}``."""

    HEAL = JobType.HEAL.value
    METRICS = JobType.METRICS.value

    @staticmethod
    def of(job_type: JobType, subject: Optional[str] = None) -> str:
        if not subject:
            return job_type.value
        return f"{job_type.value}:{subject}"


class QueuePolicy(Enum):
    SKIP_IF_RUNNING = "skipIfRunning"
    QUEUE = "queue"
    REPLACE = "replace"


@dataclass(frozen=True)
class JobSpec:
    job_id: str
    schedule: Schedule
    timeout_seconds: float
    queue_policy: QueuePolicy
    run: Callable[[], None]


@dataclass(frozen=True)
class JobRequest:
    """One-shot request; uses the registered JobSpec's timeout / policy / run."""

    job_id: str
