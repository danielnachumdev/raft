"""Remove leftover Compose-project containers that block ``raft down`` / network."""

from __future__ import annotations

import logging
from typing import List

from raft.models.app import COMPOSE_PROJECT

from ..shell import Shell

logger = logging.getLogger(__name__)


class ComposeProjectCleanup:
    """Force-remove containers labeled with this Compose project."""

    def __init__(self, shell: Shell, *, project: str = COMPOSE_PROJECT) -> None:
        self._sh = shell
        self._project = project

    def remove_labeled(self) -> List[str]:
        """``docker rm -f`` every container with ``com.docker.compose.project``."""
        ids = self._labeled_ids()
        removed: List[str] = []
        for container_id in ids:
            name = self._name_for(container_id)
            self._sh.docker("rm", "-f", container_id, check=False, capture=True)
            removed.append(name or container_id[:12])
        if removed:
            logger.info("removed leftover project containers: %s", ", ".join(removed))
        return removed

    def network_holders(self, network: str) -> List[str]:
        """Container names still attached to ``network`` (empty if inspect fails)."""
        result = self._sh.docker(
            "network",
            "inspect",
            network,
            "--format",
            "{{range .Containers}}{{.Name}} {{end}}",
            check=False,
            capture=True,
        )
        if result.returncode != 0 or not (result.stdout or "").strip():
            return []
        return [part for part in result.stdout.split() if part]

    def _labeled_ids(self) -> List[str]:
        result = self._sh.docker(
            "ps",
            "-aq",
            "--filter",
            f"label=com.docker.compose.project={self._project}",
            check=False,
            capture=True,
        )
        if result.returncode != 0 or not (result.stdout or "").strip():
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def _name_for(self, container_id: str) -> str:
        result = self._sh.docker(
            "inspect",
            "-f",
            "{{.Name}}",
            container_id,
            check=False,
            capture=True,
        )
        raw = (result.stdout or "").strip()
        return raw.lstrip("/") if raw else ""
