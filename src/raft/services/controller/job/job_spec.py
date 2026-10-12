"""Registered periodic job contract for the orchestrator."""

from dataclasses import dataclass
from typing import Callable

from ..schedule import Schedule
from .queue_policy import QueuePolicy


@dataclass(frozen=True)
class JobSpec:
    job_id: str
    schedule: Schedule
    timeout_seconds: float
    queue_policy: QueuePolicy
    run: Callable[[], None]
