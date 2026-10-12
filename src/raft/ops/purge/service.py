"""Purge Docker artifacts unused by the current runtime (`raft purge`)."""

from typing import Optional

from ...adapters.docker.prune import DockerPrune
from ...adapters.shell import Shell
from ...locking import StackLock
from ...models.stack import Stack
from ...ui import OperatorSay
from ..status.formatters import StatusFormatters
from .result import PurgeResult


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
        OperatorSay.say("Purging unused Docker images and build cache…", style="info")
        result = self.execute()
        self._report(result)
        return result

    def execute(self) -> PurgeResult:
        """Purge under ``stack.lock``; return reclaim totals (no terminal I/O)."""
        with StackLock(self.stack.root):
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
            OperatorSay.say("OK: nothing to reclaim (0B)", style="ok")
            return
        images = StatusFormatters.bytes(result.image_bytes)
        builder = StatusFormatters.bytes(result.builder_bytes)
        OperatorSay.say(
            f"OK: reclaimed {result.reclaimed_human} "
            f"(images {images}, build cache {builder})",
            style="ok",
        )
