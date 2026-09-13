"""Compose healthchecks and runtime readiness waits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..adapters.http import HttpProbe
from ..models.app import App
from ..models.manifest import AppSpec
from ..models.ports import PortSpec
from ..models.stack import Stack


@dataclass(frozen=True)
class ReadinessStrategy:
    kind: str
    port: Optional[PortSpec] = None
    path: str = "/"

    @classmethod
    def from_spec(cls, spec: AppSpec) -> "ReadinessStrategy":
        readiness = spec.readiness
        if readiness.type == "none":
            return cls(kind="none")
        port = readiness.resolve_port(spec.ports)
        return cls(kind=readiness.type, port=port, path=readiness.path)

    def healthcheck_test(self) -> Optional[list[str]]:
        if self.kind == "none" or self.port is None:
            return None
        if self.kind == "http":
            path = self.path if self.path.startswith("/") else f"/{self.path}"
            return [
                "CMD",
                "wget",
                "-qO-",
                f"http://127.0.0.1:{self.port.container_port}{path}",
            ]
        if self.kind == "tcp":
            return [
                "CMD-SHELL",
                f"nc -z 127.0.0.1 {self.port.container_port} || exit 1",
            ]
        raise ValueError(f"unknown readiness kind {self.kind!r}")

    def wait_predicate(
        self,
        app: App,
        stack: Stack,
        http: HttpProbe,
        *,
        tcp_ok: Optional[Callable[[int], bool]] = None,
    ) -> Optional[Callable[[], bool]]:
        if self.kind == "none":
            return None
        if self.kind == "http":
            return lambda: http.public_host_ok(app)
        if self.kind == "tcp":
            assert self.port is not None
            port_num = self.port.public_port or self.port.container_port
            if tcp_ok is not None:
                return lambda: tcp_ok(port_num)
            return lambda: http.tcp_port_ok(port_num)
        raise ValueError(f"unknown readiness kind {self.kind!r}")
