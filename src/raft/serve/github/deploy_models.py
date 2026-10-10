"""In-memory deploy job types for serve GitHub assist."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DeployStep:
    name: str
    status: str = "pending"
    detail: str = ""


@dataclass
class DeployJob:
    id: str
    full_name: str
    ref: str
    status: str = "pending"
    error: Optional[str] = None
    app_name: Optional[str] = None
    steps: List[DeployStep] = field(default_factory=list)
    next_steps: List[Dict[str, str]] = field(default_factory=list)
    deploy_pubkey: Optional[str] = None
    ci_pr: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "ref": self.ref,
            "status": self.status,
            "error": self.error,
            "app_name": self.app_name,
            "steps": [{"name": s.name, "status": s.status, "detail": s.detail} for s in self.steps],
            "next_steps": self.next_steps,
            "deploy_pubkey": self.deploy_pubkey,
            "ci_pr": self.ci_pr,
            "created_at": self.created_at,
        }


class DeployJobStore:
    """Process-local job map (serve is single-process)."""

    def __init__(self) -> None:
        self._jobs: Dict[str, DeployJob] = {}
        self._lock = threading.Lock()

    def create(self, full_name: str, ref: str) -> DeployJob:
        job = DeployJob(id=secrets.token_hex(8), full_name=full_name, ref=ref)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[DeployJob]:
        with self._lock:
            return self._jobs.get(job_id)
