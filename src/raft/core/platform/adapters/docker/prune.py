"""Docker Engine prune helpers for unused images and build cache."""

from raft.core.core.errors.checked import CheckedCommands
from ..shell import Shell
from .prune_reclaim import DockerPruneReclaim


class DockerPrune:
    """Prune images unused by any container, plus unused build cache.

    Does **not** prune volumes (App data). Images still referenced by stopped
    or running containers are kept by Engine ``image prune -a``.
    """

    def __init__(self, shell: Shell) -> None:
        self._sh = shell

    def unused_images(self) -> int:
        """``docker image prune -af``; return reclaimed bytes."""
        result = CheckedCommands.run_docker(
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
