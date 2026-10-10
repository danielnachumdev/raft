"""Purge Docker artifacts unused by the current runtime (`raft purge`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from raft.adapters.docker.prune import DockerPrune
from raft.adapters.shell import Shell
from raft.models.stack import Stack
from raft.services.deploy.locking import stack_lock
from raft.services.ops.status.formatters import StatusFormatters
from raft.ui import say


@dataclass(frozen=True)
class PurgeResult:
    """Space reclaimed by one purge run."""

    reclaimed_bytes: int
    image_bytes: int
    builder_bytes: int

    @property
    def reclaimed_human(self) -> str:
        return StatusFormatters.bytes(self.reclaimed_bytes)

    def as_api(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "action": "purge",
            "reclaimed_bytes": self.reclaimed_bytes,
            "reclaimed_human": self.reclaimed_human,
            "images_bytes": self.image_bytes,
            "builder_bytes": self.builder_bytes,
        }


class Purge:
    """Remove unused Docker images and build cache; report reclaim.

    Holds ``stack.lock`` so prune does not race cutover/render. Skips volumes.
    """

    def __init__(
        self,
        stack: Stack,
        *,
        shell: Optional[Shell] = None,
        docker_prune: Optional[DockerPrune] = None,
    ) -> None:
        self.stack = stack
        self._sh = shell or Shell(stack.root)
        self._prune = docker_prune or DockerPrune(self._sh)

    def run(self) -> PurgeResult:
        """Execute purge and print a human reclaim summary."""
        say("Purging unused Docker images and build cache…", style="info")
        result = self.execute()
        self._report(result)
        return result

    def execute(self) -> PurgeResult:
        """Purge under ``stack.lock``; return reclaim totals (no terminal I/O)."""
        with stack_lock(self.stack.root):
            return self._purge_unlocked()

    def _purge_unlocked(self) -> PurgeResult:
        image_bytes = self._prune.unused_images()
        builder_bytes = self._prune.build_cache()
        total = image_bytes + builder_bytes
        return PurgeResult(
            reclaimed_bytes=total,
            image_bytes=image_bytes,
            builder_bytes=builder_bytes,
        )

    @staticmethod
    def _report(result: PurgeResult) -> None:
        if result.reclaimed_bytes <= 0:
            say("OK: nothing to reclaim (0B)", style="ok")
            return
        images = StatusFormatters.bytes(result.image_bytes)
        builder = StatusFormatters.bytes(result.builder_bytes)
        say(
            f"OK: reclaimed {result.reclaimed_human} "
            f"(images {images}, build cache {builder})",
            style="ok",
        )
