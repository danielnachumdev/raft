"""Controller prereq smoke checks (Docker + data home)."""

from __future__ import annotations

import logging
from pathlib import Path

from raft.adapters.shell import Shell
from raft.models.stack import load_stack

__all__ = ["run_prereq_smoke"]

logger = logging.getLogger(__name__)


def run_prereq_smoke(home: Path, sh: Shell) -> None:
    """Verify Docker API + Compose project + registry are reachable."""
    version = sh.docker(
        "version",
        "--format",
        "{{.Server.Version}}",
        capture=True,
    )
    server = (version.stdout or "").strip() or "(unknown)"
    logger.info("docker engine reachable version=%s", server)

    compose = sh.compose("version", capture=True, check=False)
    if compose.returncode != 0:
        raise RuntimeError(
            "docker compose plugin missing or broken inside raft-controller.\n"
            "Fix: rebuild raft-controller image (`raft down && raft up`)"
        )
    logger.info("docker compose reachable")

    stack = load_stack(home)
    logger.info(
        "data home ok root=%s apps=%s core=%s",
        home,
        len(stack.apps),
        ",".join(stack.core_services),
    )
