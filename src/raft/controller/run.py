"""``raft-controller`` process entry (prereq smoke, then idle)."""

from __future__ import annotations

import logging
import time

from raft.adapters.shell import Shell
from raft.config.logging import setup_logging
from raft.config.paths import ensure_raft_home, raft_home
from raft.config.settings import load_config

from .smoke import run_prereq_smoke

__all__ = ["main"]

logger = logging.getLogger(__name__)

# Idle until Phase 1 heal lands; keep the process alive for Compose.
_IDLE_SECONDS = 3600


def main() -> None:
    home = ensure_raft_home(raft_home())
    setup_logging(home, load_config(home))
    logger.info("raft-controller starting data_home=%s", home)
    run_prereq_smoke(home, Shell(home))
    logger.info("prereq smoke ok; idle (heal/scale not implemented)")
    while True:
        time.sleep(_IDLE_SECONDS)
