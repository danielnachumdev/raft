"""Docker Engine prune helpers for unused images and build cache."""

from __future__ import annotations

import re

from raft.adapters.host.docker_stats import DockerStatsText
from raft.adapters.shell import Shell
from raft.errors.checked import run_docker_checked


class DockerPruneReclaim:
    """Parse ``Total reclaimed space: …`` lines from docker prune output."""

    _LINE = re.compile(
        r"Total reclaimed space:\s*(.+?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )

    @classmethod
    def parse(cls, text: str) -> int:
        """Return reclaimed bytes from prune stdout (0 when absent/unparsed)."""
        match = cls._LINE.search(text or "")
        if match is None:
            return 0
        parsed = DockerStatsText.parse_size(match.group(1).strip())
        return int(parsed) if parsed is not None else 0


class DockerPrune:
    """Prune images unused by any container, plus unused build cache.

    Does **not** prune volumes (App data). Images still referenced by stopped
    or running containers are kept by Engine ``image prune -a``.
    """

    def __init__(self, shell: Shell) -> None:
        self._sh = shell

    def unused_images(self) -> int:
        """``docker image prune -af``; return reclaimed bytes."""
        result = run_docker_checked(
            self._sh,
            ("image", "prune", "-af"),
            action="prune unused images",
            hint="raft doctor",
        )
        return DockerPruneReclaim.parse(result.stdout or "")

    def build_cache(self) -> int:
        """``docker builder prune -af``; return reclaimed bytes (0 if unavailable)."""
        result = self._sh.docker(
            "builder",
            "prune",
            "-af",
            check=False,
            capture=True,
        )
        if result.returncode != 0:
            return 0
        return DockerPruneReclaim.parse(result.stdout or "")
