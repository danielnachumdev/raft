"""Hold an exclusive flock on a background thread for contention tests."""

import threading
from pathlib import Path
from typing import Optional

from raft.core.platform.locking import ExclusiveLock


class LockHoldThread:
    """Acquire ``path`` in a daemon thread until ``release`` is set."""

    def __init__(self, path: Path, *, kind: str = "stack", timeout: float = 5) -> None:
        self.path = path
        self.kind = kind
        self.timeout = timeout
        self.held = threading.Event()
        self.release = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> "LockHoldThread":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        assert self.held.wait(timeout=2)
        return self

    def stop(self) -> None:
        self.release.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        with ExclusiveLock(self.path, kind=self.kind, timeout=self.timeout):
            self.held.set()
            self.release.wait(timeout=self.timeout)
