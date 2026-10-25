"""Persist / clear in-flight host oneshot job ids under ``host/locks/``."""

import json
import logging
from pathlib import Path
from typing import Optional

from raft.core.platform.locking import LockPaths

logger = logging.getLogger(__name__)


class HostOneshotFlightState:
    """JSON flight record: ``{job_id}`` for coalesce checks."""

    def __init__(self, root: Path, kind: str) -> None:
        self.path = LockPaths(root).host_job_flight(kind)

    def read_job_id(self) -> Optional[str]:
        if not self.path.is_file():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.debug("host oneshot flight state unreadable path=%s", self.path)
            return None
        if not isinstance(data, dict):
            return None
        job_id = data.get("job_id")
        if not isinstance(job_id, str) or not job_id.strip():
            return None
        return job_id.strip()

    def write_job_id(self, job_id: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"job_id": job_id}, sort_keys=True)
        self.path.write_text(payload + "\n", encoding="utf-8")

    def clear(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            logger.debug("host oneshot flight clear failed path=%s", self.path)
