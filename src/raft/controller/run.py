"""``raft-controller`` process entry (prereq smoke, then idle)."""

from __future__ import annotations

import logging
import time

from raft.adapters.shell import Shell
from raft.config.logging import setup_logging
from raft.config.paths import raft_home
from raft.config.settings import load_config
from raft.errors import OperatorError

from .smoke import run_prereq_smoke

__all__ = ["main"]

logger = logging.getLogger(__name__)

# Idle until Phase 1 heal lands; keep the process alive for Compose.
_IDLE_SECONDS = 3600


def main() -> None:
    # Host CLI owns ``ensure_raft_home`` / template sync. The controller only
    # consumes the mounted data home (package is on PYTHONPATH, not a pip dist).
    home = raft_home()
    if not home.is_dir():
        raise OperatorError(
            f"raft data home missing: {home}\n"
            f"Fix: run `raft render` (or any raft command) on the host first"
        )
    setup_logging(home, load_config(home))
    logger.info("raft-controller starting data_home=%s", home)
    run_prereq_smoke(home, Shell(home))
    logger.info("prereq smoke ok; idle (heal/scale not implemented)")
    while True:
        time.sleep(_IDLE_SECONDS)
