"""Per-thread nesting map for re-entrant FIFO locks."""

import threading
from typing import Set


class ThreadHeldFifos:
    """Thread-local FIFO lock keys so same-thread re-entry skips a second ticket."""

    _local = threading.local()

    @classmethod
    def keys(cls) -> Set[str]:
        held = getattr(cls._local, "keys", None)
        if held is None:
            held = set()
            cls._local.keys = held
        return held

    @classmethod
    def hold(cls, key: str) -> None:
        cls.keys().add(key)

    @classmethod
    def release(cls, key: str) -> None:
        cls.keys().discard(key)

    @classmethod
    def holds(cls, key: str) -> bool:
        return key in cls.keys()
