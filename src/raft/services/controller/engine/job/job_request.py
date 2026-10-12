"""One-shot job enqueue request."""

from dataclasses import dataclass


@dataclass(frozen=True)
class JobRequest:
    """One-shot request; uses the registered JobSpec's timeout / policy / run."""

    job_id: str
