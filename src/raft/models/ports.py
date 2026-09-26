"""App port exposure: container ports and how they reach the public edge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from raft.errors import require_bool, require_int

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
                f"{path}: ports[{self.name!r}].publicPort out of range: " f"{self.public_port}"
            )

    def _validate_public_port_rules(self, *, path: Path) -> None:
        if self.expose in {"stream", "host"} and self.public_port is None:
            raise ValueError(
                f"{path}: ports[{self.name!r}].publicPort is required when "
                f"expose={self.expose!r}"
            )
        if self.expose in {"http", "none"} and self.public_port is not None:
            raise ValueError(
                f"{path}: ports[{self.name!r}].publicPort is only valid for " f"expose stream|host"
            )
        if self.proxy_protocol and self.expose != "stream":
            raise ValueError(
                f"{path}: ports[{self.name!r}].proxyProtocol only applies to " f"expose=stream"
            )


class PortListParser:
    """Parse ``spec.ports`` into validated :class:`PortSpec` tuples."""

    def parse(self, spec: dict[str, Any], path: Path) -> tuple[PortSpec, ...]:
        raw = spec.get("ports")
        if raw is None:
            raise ValueError(f"{path}: spec.ports is required (non-empty list)")
        if not isinstance(raw, list) or not raw:
            raise ValueError(f"{path}: spec.ports must be a non-empty list")
        if "port" in spec:
            raise ValueError(f"{path}: spec.port is not supported; use spec.ports[]")
        ports: list[PortSpec] = []
        seen: set[str] = set()
        for index, entry in enumerate(raw):
            ports.append(self._parse_entry(entry, index=index, path=path, seen=seen))
        return tuple(ports)

    def _parse_entry(
        self,
        entry: Any,
        *,
        index: int,
        path: Path,
        seen: set[str],
    ) -> PortSpec:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: spec.ports[{index}] must be an object")
        name = self._entry_name(entry, index=index, path=path, seen=seen)
        if "containerPort" not in entry:
            raise ValueError(f"{path}: spec.ports[{name!r}].containerPort is required")
        port = self._build_port(entry, name=name, path=path)
        port.validate(path=path)
        return port

    def _build_port(self, entry: dict, *, name: str, path: Path) -> PortSpec:
        return PortSpec(
            name=name,
            container_port=require_int(
                entry["containerPort"],
                label=f"spec.ports[{name!r}].containerPort",
                path=path,
            ),
            expose=str(entry.get("expose", "http")).strip().lower() or "http",
            public_port=self._public_port(entry, name=name, path=path),
            protocol=str(entry.get("protocol", "tcp")).strip().lower() or "tcp",
            proxy_protocol=require_bool(
                entry.get("proxyProtocol", False),
                label=f"spec.ports[{name!r}].proxyProtocol",
                path=path,
            ),
        )

    @staticmethod
    def _entry_name(entry: dict, *, index: int, path: Path, seen: set[str]) -> str:
        name = str(entry.get("name", "")).strip()
        if not name:
            raise ValueError(f"{path}: spec.ports[{index}].name is required")
        if name in seen:
            raise ValueError(f"{path}: duplicate port name {name!r}")
        seen.add(name)
        return name

    @staticmethod
    def _public_port(entry: dict, *, name: str, path: Path) -> Optional[int]:
        public_raw = entry.get("publicPort")
        if public_raw is None:
            return None
        return require_int(public_raw, label=f"spec.ports[{name!r}].publicPort", path=path)


def parse_ports(spec: dict[str, Any], path: Path) -> tuple[PortSpec, ...]:
    return PortListParser().parse(spec, path)


def port_by_name(ports: tuple[PortSpec, ...], name: str) -> PortSpec:
    for port in ports:
        if port.name == name:
            return port
    known = ", ".join(p.name for p in ports) or "(none)"
    raise KeyError(f"unknown port {name!r} (known: {known})")
