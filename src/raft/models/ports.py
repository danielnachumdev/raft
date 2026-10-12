"""App port exposure: container ports and how they reach the public edge."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

EXPOSE_MODES = frozenset({"http", "stream", "host", "none"})
PORT_PROTOCOLS = frozenset({"tcp", "udp"})


@dataclass(frozen=True)
class PortSpec:
    name: str
    container_port: int
    expose: str
    public_port: Optional[int] = None
    protocol: str = "tcp"
    proxy_protocol: bool = False

    def validate(self, *, path: Path) -> None:
        self._validate_enums(path=path)
        self._validate_ranges(path=path)
        self._validate_public_port_rules(path=path)

    def _validate_enums(self, *, path: Path) -> None:
        if self.expose not in EXPOSE_MODES:
            raise ValueError(
                f"{path}: ports[{self.name!r}].expose must be one of "
                f"{sorted(EXPOSE_MODES)}, got {self.expose!r}"
            )
        if self.protocol not in PORT_PROTOCOLS:
            raise ValueError(
                f"{path}: ports[{self.name!r}].protocol must be one of "
                f"{sorted(PORT_PROTOCOLS)}, got {self.protocol!r}"
            )

    def _validate_ranges(self, *, path: Path) -> None:
        if not (1 <= self.container_port <= 65535):
            raise ValueError(
                f"{path}: ports[{self.name!r}].containerPort out of range: "
                f"{self.container_port}"
            )
        if self.public_port is not None and not (1 <= self.public_port <= 65535):
            raise ValueError(
                f"{path}: ports[{self.name!r}].publicPort out of range: "
                f"{self.public_port}"
            )

    def _validate_public_port_rules(self, *, path: Path) -> None:
        if self.expose in {"stream", "host"} and self.public_port is None:
            raise ValueError(
                f"{path}: ports[{self.name!r}].publicPort is required when "
                f"expose={self.expose!r}"
            )
        if self.expose in {"http", "none"} and self.public_port is not None:
            raise ValueError(
                f"{path}: ports[{self.name!r}].publicPort is only valid for "
                f"expose stream|host"
            )
        if self.proxy_protocol and self.expose != "stream":
            raise ValueError(
                f"{path}: ports[{self.name!r}].proxyProtocol only applies to "
                f"expose=stream"
            )

    @staticmethod
    def by_name(ports: tuple["PortSpec", ...], name: str) -> "PortSpec":
        for port in ports:
            if port.name == name:
                return port
        known = ", ".join(p.name for p in ports) or "(none)"
        raise KeyError(f"unknown port {name!r} (known: {known})")
