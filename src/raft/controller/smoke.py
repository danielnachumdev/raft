"""Controller prereq smoke checks (Docker + data home)."""

from __future__ import annotations

import logging
from pathlib import Path

from raft.adapters.shell import Shell
from raft.models.stack import Stack

__all__ = ["run_prereq_smoke"]

logger = logging.getLogger(__name__)


def run_prereq_smoke(home: Path, sh: Shell) -> None:
    """Verify Docker API + Compose plugin + registry are readable."""
    _smoke_docker(sh)
    _smoke_compose(sh)
    # Stack.load_apps skips ensure_raft_home: data home is mounted :ro.
    stack = Stack.load_apps(home)
    logger.info(
        "data home ok root=%s apps=%s core=%s",
        home,
        len(stack.apps),
        ",".join(stack.core_services),
    )


def _smoke_docker(sh: Shell) -> None:
    version = sh.docker("version", "--format", "{{.Server.Version}}", capture=True)
    server = (version.stdout or "").strip() or "(unknown)"
    logger.info("docker engine reachable version=%s", server)


def _smoke_compose(sh: Shell) -> None:
    compose = sh.compose("version", capture=True, check=False)
    if compose.returncode != 0:
        raise RuntimeError(
            "docker compose plugin missing or broken inside raft-controller.\n"
            "Fix: rebuild raft-controller image (`raft down && raft up`)"
        )
    logger.info("docker compose reachable")
