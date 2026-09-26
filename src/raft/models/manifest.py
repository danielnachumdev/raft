"""App manifest types (AppSpec / VolumeSpec) and path constants.

Prefer ``AppDocument`` / ``AppRegistry`` for parse and registry I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ports import PortSpec
from .readiness_spec import ReadinessSpec
from .scaling_spec import ScalingSpec

CONTRACT_API_VERSION = "raft/v1"
CONTRACT_KIND = "App"
CONTRACT_REL_PATH = Path(".raft") / "app.yaml"
REGISTRY_DIR = Path("state") / "apps"
TLS_MODES = frozenset({"off", "origin"})


@dataclass(frozen=True)
class VolumeSpec:
    host_path: str
    container_path: str
    read_only: bool = False
    name: Optional[str] = None


@dataclass(frozen=True)
class AppSpec:
    ports: tuple[PortSpec, ...]
    tls: str = "off"
    readiness: ReadinessSpec = ReadinessSpec()
    www: bool = True
    extra_hosts: tuple[str, ...] = ()
    build_context: Optional[str] = None
    dockerfile: Optional[str] = None
    cpus_limit: str = "0.50"
    memory_limit: str = "128M"
    cpus_reservation: str = "0.10"
    memory_reservation: str = "32M"
    metadata_name: Optional[str] = None
    group: Optional[str] = None
    depends_on: tuple[str, ...] = ()
    env_file: Optional[str] = None
    env: tuple[tuple[str, str], ...] = ()
    volumes: tuple[VolumeSpec, ...] = ()
    scaling: Optional[ScalingSpec] = None

    def server_names(self, public_host: str) -> tuple[str, ...]:
        names: list[str] = [public_host]
        if self.www:
            names.append(f"www.{public_host}")
        names.extend(h.strip() for h in self.extra_hosts if h.strip())
        return self._unique_names(names)

    @staticmethod
    def _unique_names(names: list[str]) -> tuple[str, ...]:
        seen: set[str] = set()
        out: list[str] = []
        for name in names:
            if name not in seen:
                seen.add(name)
                out.append(name)
        return tuple(out)

    def http_ports(self) -> tuple[PortSpec, ...]:
        return tuple(p for p in self.ports if p.expose == "http")

    def stream_ports(self) -> tuple[PortSpec, ...]:
        return tuple(p for p in self.ports if p.expose == "stream")

    def host_ports(self) -> tuple[PortSpec, ...]:
        return tuple(p for p in self.ports if p.expose == "host")

    def none_ports(self) -> tuple[PortSpec, ...]:
        return tuple(p for p in self.ports if p.expose == "none")
