"""``raft-controller`` process entry (prereq smoke, then heal loop)."""

from __future__ import annotations

import logging

from raft.adapters.docker import DockerStack
from raft.adapters.shell import Shell
from raft.config.paths import raft_home
from raft.config.settings import load_config
from raft.errors import OperatorError
from raft.models.stack import Stack

from .heal import run_heal_forever
from .logging import setup_controller_logging
from .smoke import run_prereq_smoke

__all__ = ["main"]

logger = logging.getLogger(__name__)


def main() -> None:
    # Host CLI owns ``ensure_raft_home`` / template sync. The controller only
    # consumes the mounted data home (package is on PYTHONPATH, not a pip dist).
    home = raft_home()
    if not home.is_dir():
        raise OperatorError(
            f"raft data home missing: {home}\n"
            f"Fix: run `raft render` (or any raft command) on the host first"
        )
    config = load_config(home)
    setup_controller_logging(config)
    logger.info("raft-controller starting data_home=%s", home)
    sh = Shell(home)
    run_prereq_smoke(home, sh)
    logger.info("prereq smoke ok; entering heal loop")
    stack = Stack(root=home, apps=())
    docker = DockerStack(stack, sh)
    run_heal_forever(home, config.healing, docker)
