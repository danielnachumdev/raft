"""Re-render gate TLS/HTTP and reload nginx after ACME material changes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from raft.locking.locking import stack_lock
from raft.render import StackRenderer
from raft.render.gate_nginx import GateNginxStamp

from raft.models.stack import Stack

if TYPE_CHECKING:
    from raft.adapters.docker import DockerStack

logger = logging.getLogger(__name__)


class AcmeGateInstall:
    """After new ``acme.{pem,key}`` bytes: render snippets and ``nginx -s reload``."""

    def __init__(self, stack: Stack, docker: Optional["DockerStack"] = None) -> None:
        self.stack = stack
        self.docker = docker

    def apply(self) -> None:
        """Hold ``stack.lock`` only around render + gate nginx reload."""
        with stack_lock(self.stack.root):
            self._apply_locked()

    def _apply_locked(self) -> None:
        StackRenderer(self.stack).render()
        if self.docker is None:
            return
        if self.stack.gate not in self.docker.running_services():
            logger.info("ACME install: gate not running; skipped nginx reload")
            return
        self.docker.reload_gate_nginx()
        stamp = GateNginxStamp(self.stack.root)
        stamp.write(stamp.fingerprint())
        logger.info("ACME install: reloaded gate nginx")
