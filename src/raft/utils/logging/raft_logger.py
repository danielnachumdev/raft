"""Shared ``raft`` logger root configuration."""

import logging


class RaftLogger:
    """Configure the process ``raft`` logger root (handlers cleared)."""

    NAME = "raft"

    def configure(self, level: int) -> logging.Logger:
        root = logging.getLogger(self.NAME)
        root.handlers.clear()
        root.setLevel(level)
        root.propagate = False
        return root

    def clear(self) -> None:
        root = logging.getLogger(self.NAME)
        root.handlers.clear()
        root.propagate = True
        root.setLevel(logging.NOTSET)
