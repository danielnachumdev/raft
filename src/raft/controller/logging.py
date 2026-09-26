"""Controller logging — stdout only (data home may be mounted read-only)."""

from __future__ import annotations

import logging
import sys

from raft.config.settings_types import RaftConfig

__all__ = ["setup_controller_logging"]


def setup_controller_logging(config: RaftConfig) -> None:
    """Log to the container stdout (picked up by ``docker compose logs``).

    Do not open ``~/.raft/logs``: the controller runs as root with a bind-mounted
    data home, and file handlers would create root-owned files the host CLI
    cannot replace.
    """
    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    root = logging.getLogger("raft")
    root.handlers.clear()
    root.setLevel(level)
    root.propagate = False
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
