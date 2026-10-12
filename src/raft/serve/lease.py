"""Exclusive flock lease for one ``raft serve`` port."""

import fcntl
import os
from pathlib import Path


class ServeLease:
    """Exclusive flock held for the lifetime of a foreground ``raft serve``."""

    def __init__(self, path: Path, fd: int) -> None:
        self.path = path
        self.fd = fd
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        try:
            os.ftruncate(self.fd, 0)
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
            self._unlink_quiet(self.path)

    @staticmethod
    def _unlink_quiet(path: Path) -> None:
        try:
            path.unlink()
        except OSError:
            pass
