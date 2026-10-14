"""Docker ``logs --timestamps`` adapter for :class:`ServiceLogsCapture`."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from raft.core.platform.adapters.docker.stack import DockerStack


class DockerContainerLogSource:
    """Fetch timestamped logs for a container id or name via ``DockerStack``."""

    def __init__(self, docker: "DockerStack") -> None:
        self._docker = docker

    def fetch(self, container: str, *, since: str) -> str:
        return self._docker.container_logs_since(container, since=since)
