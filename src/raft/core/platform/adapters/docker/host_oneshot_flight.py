"""Single-flight coalesce for detached ``HostOneshot.start`` jobs."""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from raft.core.core.errors.cta import OperatorError
from raft.core.platform.adapters.shell import Shell
from raft.core.platform.locking import FifoLock, HostJobKinds
from raft.core.platform.locking.timeout import LockTimeout

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
    Host CLI callers can ``join_alive`` to wait for that job instead of
    queueing a second rebuild behind ``stack.lock``.
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

    def peek_alive(self) -> Optional[str]:
        """Living oneshot job id, or ``None`` after clearing a stale record."""
        with FifoLock(self.root, f"host-job-{self.kind}"):
            return self._coalesce_alive()

    def join_alive(
        self,
        job_id: Optional[str] = None,
        *,
        poll_seconds: float = 2.0,
        timeout: Optional[float] = None,
    ) -> Optional[HostOneshotStart]:
        """Wait out a living oneshot; ``None`` when nothing is in flight."""
        cid = job_id or self.peek_alive()
        if cid is None:
            return None
        budget = timeout if timeout is not None else LockTimeout.resolve() * 2
        self.wait_until_done(cid, poll_seconds=poll_seconds, timeout=budget)
        self._state.clear()
        logger.info(
            "host oneshot flight joined kind=%s job_id=%s",
            self.kind,
            cid,
        )
        return HostOneshotStart(job_id=cid, coalesced=True)

    def wait_until_done(
        self,
        job_id: str,
        *,
        poll_seconds: float = 2.0,
        timeout: float,
    ) -> None:
        """Poll until ``job_id`` is no longer a running container."""
        deadline = time.monotonic() + timeout
        while self._alive.running(job_id):
            if time.monotonic() >= deadline:
                raise OperatorError(
                    f"timed out waiting for in-flight host job {job_id[:12]}… "
                    f"(waited {timeout:.0f}s).\n"
                    "Fix: check `docker ps` for a stuck oneshot, or retry "
                    "`raft redeploy dashboard` after it exits."
                )
            time.sleep(poll_seconds)

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
