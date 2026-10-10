"""Reset the ``raft`` logger between tests."""

from __future__ import annotations

from raft.utils.logging.raft_logger import RaftLogger


class LoggingReset:
    """Clear host/controller logging state for isolated tests."""

    def for_tests(self) -> None:
        RaftLogger().clear()
