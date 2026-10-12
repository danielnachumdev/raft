"""Re-render gate TLS/HTTP and reload nginx after ACME material changes."""

import logging
from typing import TYPE_CHECKING, Optional

from raft.core.platform.locking import StackLock
from raft.core.core.models.stack import Stack
from raft.core.lifecycle.render.gate_nginx import GateNginxStamp
from raft.core.lifecycle.render.stack_renderer import StackRenderer

if TYPE_CHECKING:
    from ..adapters.docker.stack import DockerStack

logger = logging.getLogger(__name__)


class AcmeGateInstall:
    """After new ``acme.{pem,key}`` bytes: render snippets and ``nginx -s reload``."""

    def __init__(self, stack: Stack, docker: Optional["DockerStack"] = None) -> None:
        self.stack = stack
        self.docker = docker

    def apply(self) -> None:
        """Hold ``stack.lock`` only around render + gate nginx reload."""
        with StackLock(self.stack.root):
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
