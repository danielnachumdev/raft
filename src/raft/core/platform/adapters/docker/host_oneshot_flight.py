"""Single-flight coalesce for detached ``HostOneshot.start`` jobs."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from raft.core.platform.adapters.shell import Shell
from raft.core.platform.locking import FifoLock, HostJobKinds

from .host_oneshot import HostOneshot
from .host_oneshot_alive import HostOneshotAlive
from .host_oneshot_flight_state import HostOneshotFlightState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HostOneshotStart:
    """Result of a coalesced or freshly started oneshot."""

    job_id: str
    coalesced: bool


class HostOneshotFlight:
    """Claim at most one in-flight detached oneshot per kind.

    Concurrent starters take a short ``FifoLock`` (true FCFS ticket order) only
    to read/write flight state and optionally call ``HostOneshot.start``. The
    lock is released before the child rebuild runs, so the oneshot process can
    take ``stack.lock`` without deadlocking against the parent.

    If a recorded job_id is still a running container, later starters return
    that same id (``coalesced=True``) instead of spawning another oneshot.
    """

    KIND_DASHBOARD_REDEPLOY = HostJobKinds.DASHBOARD_REDEPLOY

    def __init__(
        self,
        root: Path,
        kind: str,
        *,
        shell: Optional[Shell] = None,
        oneshot: Optional[HostOneshot] = None,
        alive: Optional[HostOneshotAlive] = None,
        state: Optional[HostOneshotFlightState] = None,
    ) -> None:
        self.root = root
        self.kind = kind
        self._shell = shell or Shell(root)
        self._oneshot = oneshot or HostOneshot(self._shell)
        self._alive = alive or HostOneshotAlive(self._shell)
        self._state = state or HostOneshotFlightState(root, kind)

    def start(
        self, argv: Sequence[str], *, with_docker: bool = True
    ) -> HostOneshotStart:
        with FifoLock(self.root, f"host-job-{self.kind}"):
            existing = self._coalesce_alive()
            if existing is not None:
                return HostOneshotStart(job_id=existing, coalesced=True)
            return self._start_fresh(argv, with_docker=with_docker)

    def _coalesce_alive(self) -> Optional[str]:
        job_id = self._state.read_job_id()
        if job_id is None:
            return None
        if self._alive.running(job_id):
            logger.info(
                "host oneshot flight coalesce kind=%s job_id=%s",
                self.kind,
                job_id,
            )
            return job_id
        self._state.clear()
        return None

    def _start_fresh(
        self, argv: Sequence[str], *, with_docker: bool
    ) -> HostOneshotStart:
        job_id = self._oneshot.start(argv, with_docker=with_docker)
        self._state.write_job_id(job_id)
        logger.info(
            "host oneshot flight started kind=%s job_id=%s",
            self.kind,
            job_id,
        )
        return HostOneshotStart(job_id=job_id, coalesced=False)
