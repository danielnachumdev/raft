"""Rebuild ``raft-controller`` with the host install stamp."""

import logging

from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.core.models.stack import Stack
from raft.core.core.ui import OperatorSay
from raft.core.lifecycle.render.stack_renderer import StackRenderer
from raft.core.platform.adapters.docker import DockerStack
from raft.core.platform.locking import StackLock

logger = logging.getLogger(__name__)


class ControllerRedeploy:
    """Stamp/rebuild path for ``raft redeploy controller``."""

    def __init__(self, stack: Stack, docker: DockerStack) -> None:
        self.stack = stack
        self.docker = docker

    def run(self) -> None:
        with StackLock(self.stack.root):
            self._rebuild_locked()

    def _rebuild_locked(self) -> None:
        name = self.stack.controller
        logger.info("rebuilding controller %s", name)
        StackRenderer(self.stack).render()
        self.docker.rebuild_service(name)
        GraphEventStore(self.stack.root).record_deployment(
            service=name,
            app="controller",
            ref="-",
            label="Redeploy controller",
            action="redeploy",
        )
        OperatorSay.say("controller redeployed", style="ok")
