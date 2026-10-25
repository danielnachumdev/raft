"""Docker ``logs --timestamps`` adapter for :class:`ServiceLogsCapture`."""

from typing import TYPE_CHECKING

from raft.core.platform.adapters.docker.bounded_logs import (
    DEFAULT_LOG_FETCH_BOOTSTRAP_TAIL,
    DEFAULT_LOG_FETCH_MAX_BYTES,
    DEFAULT_LOG_FETCH_TIMEOUT_SECONDS,
)

if TYPE_CHECKING:
    from raft.core.platform.adapters.docker.stack import DockerStack


class DockerContainerLogSource:
    """Fetch timestamped logs for a container id or name via ``DockerStack``."""

    def __init__(
        self,
        docker: "DockerStack",
        *,
        timeout: float = DEFAULT_LOG_FETCH_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_LOG_FETCH_MAX_BYTES,
        bootstrap_tail: int = DEFAULT_LOG_FETCH_BOOTSTRAP_TAIL,
    ) -> None:
        self._docker = docker
        self._timeout = timeout
        self._max_bytes = max_bytes
        self._bootstrap_tail = bootstrap_tail

    def fetch(self, container: str, *, since: str) -> str:
        return self._docker.container_logs_since(
            container,
            since=since,
            timeout=self._timeout,
            max_bytes=self._max_bytes,
            bootstrap_tail=self._bootstrap_tail,
        )
