"""Ticket-based exclusive lock with true FCFS grant order."""

import logging
import time
from pathlib import Path
from typing import Optional

from raft.core.core.errors.domain import DomainErrors

from .exclusive import ExclusiveLock
from .fifo_held import ThreadHeldFifos
from .paths import LockPaths
from .timeout import LockTimeout

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 0.05


class FifoLock:
    """Exclusive lock that grants waiters in arrival (ticket) order.

    Plain ``flock`` is not FIFO across waiters. This lock mints monotonically
    increasing tickets under a short ``seq`` flock, then waits until the
    caller's ticket is the lowest outstanding file under
    ``host/locks/fifo-<kind>/``. Work grant order is FCFS by ticket number.

    Re-entrant for the same thread and kind. Do not nest a FIFO kind inside
    ``stack.lock`` when the critical section (or a child process) also needs
    ``stack.lock`` — release before long work that takes stack locks.
    """

    def __init__(
        self,
        root: Path,
        kind: str,
        *,
        timeout: Optional[float] = None,
    ) -> None:
        self.root = root
        self.kind = kind
        self.budget = LockTimeout.resolve(timeout)
        self.paths = LockPaths(root)
        self.key = f"fifo:{kind}"
        self.ticket: Optional[int] = None
        self.reentered = False
        self.waited = False

    def __enter__(self) -> "FifoLock":
        if ThreadHeldFifos.holds(self.key):
            self.reentered = True
            return self
        self.ticket = self._mint_ticket()
        self._wait_until_head()
        ThreadHeldFifos.hold(self.key)
        self._log_acquired()
        return self

    def __exit__(self, *exc) -> None:
        if self.reentered or self.ticket is None:
            return
        try:
            self._drop_ticket(self.ticket)
        finally:
            ThreadHeldFifos.release(self.key)
            self.ticket = None

    def _mint_ticket(self) -> int:
        directory = self.paths.fifo(self.kind)
        directory.mkdir(parents=True, exist_ok=True)
        with ExclusiveLock(self.paths.fifo_seq(self.kind), kind=f"fifo-seq-{self.kind}"):
            next_path = self.paths.fifo_next(self.kind)
            n = self._read_next(next_path)
            next_path.write_text(str(n + 1), encoding="utf-8")
            self.paths.fifo_ticket(self.kind, n).touch()
            return n

    def _wait_until_head(self) -> None:
        assert self.ticket is not None
        deadline = time.monotonic() + self.budget
        while True:
            if self._is_head(self.ticket):
                return
            self._raise_or_wait(deadline)

    def _is_head(self, ticket: int) -> bool:
        outstanding = self._outstanding_tickets()
        return bool(outstanding) and outstanding[0] == ticket

    def _outstanding_tickets(self) -> list[int]:
        directory = self.paths.fifo(self.kind)
        if not directory.is_dir():
            return []
        found: list[int] = []
        for path in directory.iterdir():
            name = path.name
            if not name.startswith("ticket-"):
                continue
            try:
                found.append(int(name.split("-", 1)[1]))
            except ValueError:
                continue
        found.sort()
        return found

    def _drop_ticket(self, ticket: int) -> None:
        path = self.paths.fifo_ticket(self.kind, ticket)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.debug("fifo ticket unlink failed kind=%s ticket=%s", self.kind, ticket)

    def _raise_or_wait(self, deadline: float) -> None:
        if time.monotonic() >= deadline:
            path = self.paths.fifo(self.kind)
            raise DomainErrors.deploy_lock_busy(f"fifo-{self.kind}", path)
        if not self.waited:
            logger.info("waiting for fifo-%s lock", self.kind)
            self.waited = True
        time.sleep(_POLL_INTERVAL_SECONDS)

    def _log_acquired(self) -> None:
        if self.waited:
            logger.info("acquired fifo-%s lock", self.kind)
        else:
            logger.debug("acquired fifo-%s lock ticket=%s", self.kind, self.ticket)

    @staticmethod
    def _read_next(path: Path) -> int:
        if not path.is_file():
            return 0
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return 0
        try:
            return int(raw)
        except ValueError:
            return 0
