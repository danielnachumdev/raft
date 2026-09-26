"""Wait helpers over DockerStack.service_runtime for e2e harnesses."""

from __future__ import annotations

from typing import Callable, Sequence, Union

from raft.adapters.docker import DockerStack
from tests.shared.wait import Wait

_STOPPED = ("exited", "dead", "missing")


class ServiceRuntimeWait:
    """Poll ``docker.service_runtime`` until status matches."""

    def __init__(self, docker: DockerStack, service: str) -> None:
        self.docker = docker
        self.service = service

    def until_status(
        self,
        status: Union[str, Sequence[str]],
        *,
        timeout: float = 45.0,
        message: str = "",
    ) -> None:
        wanted = (status,) if isinstance(status, str) else tuple(status)
        Wait.until(
            self._predicate(wanted),
            timeout=timeout,
            message=message or self._default_message(wanted),
        )

    def until_running(self, *, timeout: float = 45.0, message: str = "") -> None:
        self.until_status("running", timeout=timeout, message=message)

    def until_stopped(self, *, timeout: float = 45.0, message: str = "") -> None:
        self.until_status(_STOPPED, timeout=timeout, message=message)

    def _predicate(self, wanted: Sequence[str]) -> Callable[[], bool]:
        service = self.service

        def ready() -> bool:
            return self.docker.service_runtime(service)[0] in wanted

        return ready

    def _default_message(self, wanted: Sequence[str]) -> str:
        return f"{self.service} wanted status in {list(wanted)!r}"
