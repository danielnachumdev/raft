"""Stable string orchestrator keys: ``{type}`` or ``{type}:{subject}``."""

from typing import Optional

from .job_type import JobType


class JobIds:
    """Stable string orchestrator keys: ``{type}`` or ``{type}:{subject}``."""

    HEAL = JobType.HEAL.value
    METRICS = JobType.METRICS.value

    @staticmethod
    def of(job_type: JobType, subject: Optional[str] = None) -> str:
        if not subject:
            return job_type.value
        return f"{job_type.value}:{subject}"
