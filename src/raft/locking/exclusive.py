"""Exclusive flock with same-thread re-entrancy and timed wait."""

import fcntl
import logging
import os
import time
from pathlib import Path
from typing import Optional

from ..errors.domain import DomainErrors
from .held import HeldLock, ThreadHeldLocks
from .timeout import LockTimeout

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 0.05


class ExclusiveLock:
    """Hold an exclusive ``flock`` on ``path`` (create parent dirs as needed).

    Re-entrant for the same thread and resolved path. Waits up to ``timeout``
    seconds for another holder; then raises ``OperatorError``.
    """

    def __init__(
        self,
        path: Path,
        *,
        kind: str,
        timeout: Optional[float] = None,
    ) -> None:
        self.path = path.resolve()
        self.kind = kind
        self.budget = LockTimeout.resolve(timeout)
        self.key = str(self.path)
        self.fd: Optional[int] = None
        self.held: Optional[HeldLock] = None
        self.waited = False
        self.reentered = False

    def __enter__(self) -> None:
        held_map = ThreadHeldLocks.map()
        if self.key in held_map:
            self.reentered = True
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o644)
        self._acquire_or_raise()
        self.held = HeldLock(self.path, self.fd)
        held_map[self.key] = self.held
        self._log_acquired()

    def __exit__(self, *exc) -> None:
        if self.reentered or self.held is None:
            return
        ThreadHeldLocks.release(self.key, self.held)

    def _log_acquired(self) -> None:
        if self.waited:
            logger.info("acquired %s lock", self.kind)
        else:
            logger.debug("acquired %s lock %s", self.kind, self.path)

    def _acquire_or_raise(self) -> None:
        assert self.fd is not None
        deadline = time.monotonic() + self.budget
        try:
            self._poll_until_locked(deadline)
        except BaseException:
            self._close_failed_fd()
            raise

    def _close_failed_fd(self) -> None:
        if self.fd is None:
            return
        try:
            os.close(self.fd)
        except OSError:
            pass
        self.fd = None

    def _poll_until_locked(self, deadline: float) -> None:
        assert self.fd is not None
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                self._raise_or_wait(deadline)

    def _raise_or_wait(self, deadline: float) -> None:
        if time.monotonic() >= deadline:
            raise DomainErrors.deploy_lock_busy(self.kind, self.path)
        if not self.waited:
            logger.info("waiting for %s lock", self.kind)
            self.waited = True
        time.sleep(_POLL_INTERVAL_SECONDS)
