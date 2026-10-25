"""Poll Compose containers and append stdout into service log dirs (#313)."""

import logging
from pathlib import Path
from typing import Sequence

from raft.core.core.config.settings.types import ServiceLogsConfig
from raft.core.core.models.stack import Stack
from raft.core.observe.ops.logs.capture import ServiceLogsCapture
from raft.core.observe.ops.logs.docker_source import DockerContainerLogSource
from raft.core.observe.ops.logs.keys import ServiceLogsKeys
from raft.core.observe.ops.logs.store import ServiceLogsStore
from raft.core.platform.adapters.docker.stack import DockerStack

logger = logging.getLogger(__name__)


class ServiceLogsShipper:
    """One controller tick: ship a bounded slice of Docker logs (round-robin)."""

    def __init__(
        self,
        home: Path,
        config: ServiceLogsConfig,
        docker: DockerStack,
        *,
        stack_loader=None,
    ) -> None:
        self.home = home
        self._config = config
        self._docker = docker
        self._stack_loader = stack_loader or (lambda: Stack.load_apps(home))
        self._rr_index = 0
        self._store = ServiceLogsStore(
            home,
            max_age_days=config.retention_max_age_days,
            max_bytes=config.retention_max_bytes,
        )
        self._capture = ServiceLogsCapture(
            self._store,
            DockerContainerLogSource(
                docker,
                timeout=config.fetch_timeout_seconds,
                max_bytes=config.max_fetch_bytes,
                bootstrap_tail=config.max_fetch_lines,
            ),
        )

    def tick(self) -> None:
        if not self._config.enabled:
            return
        stack = self._stack_loader()
        self._docker.stack = stack
        self._store.bind_apps(stack.apps)
        keys = ServiceLogsKeys(stack).known_compose_ids(
            include_edge=self._config.include_edge
        )
        for compose_id in self._slice(keys):
            self._ship_one(compose_id)

    def _slice(self, keys: Sequence[str]) -> list[str]:
        if not keys:
            return []
        budget = min(max(1, self._config.max_services_per_tick), len(keys))
        start = self._rr_index % len(keys)
        chosen = [keys[(start + i) % len(keys)] for i in range(budget)]
        self._rr_index = (start + budget) % len(keys)
        return chosen

    def _ship_one(self, compose_id: str) -> None:
        cid = self._docker.try_service_container_id(compose_id)
        if not cid:
            return
        try:
            n = self._capture.ship(compose_id, cid)
        except OSError as exc:
            logger.warning(
                "service-logs ship failed service=%s err=%s", compose_id, exc
            )
            return
        if n:
            logger.debug("service-logs shipped service=%s lines=%s", compose_id, n)
