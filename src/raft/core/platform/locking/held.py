"""Per-thread nesting map for re-entrant exclusive flocks."""

import fcntl
import logging
import os
import threading
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class HeldLock:
    """One acquired flock fd bound to a resolved path."""

    __slots__ = ("path", "fd")

    def __init__(self, path: Path, fd: int) -> None:
        self.path = path
        self.fd = fd


class ThreadHeldLocks:
    """Thread-local held flocks so same-thread re-entry skips a second flock."""

    _local = threading.local()

    @classmethod
    def map(cls) -> Dict[str, HeldLock]:
        held = getattr(cls._local, "held", None)
        if held is None:
            held = {}
            cls._local.held = held
        return held

    @classmethod
    def release(cls, key: str, held: HeldLock) -> None:
        try:
            fcntl.flock(held.fd, fcntl.LOCK_UN)
        finally:
            cls._close_fd(held.fd)
            cls.map().pop(key, None)
            logger.debug("released lock %s", held.path)

    @classmethod
    def _close_fd(cls, fd: int) -> None:
        try:
            os.close(fd)
        except OSError:
            pass
