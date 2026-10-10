"""Controller logging: stdout only (data home may be read-only)."""

from __future__ import annotations

import logging
import sys

from ...config.settings_types import RaftConfig
from .raft_logger import RaftLogger

_STDOUT_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


class ControllerLogging:
    """Controller: stdout only (mounted data home must stay host-owned)."""

    def configure(self, config: RaftConfig) -> None:
        # Do not open ``~/.raft/logs``: the controller runs as root with a
        # bind-mounted data home; file handlers would create root-owned files.
        level = getattr(logging, config.logging.level.upper(), logging.INFO)
        root = RaftLogger().configure(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(
            logging.Formatter(fmt=_STDOUT_FORMAT, datefmt=_DATEFMT)
        )
        root.addHandler(handler)
