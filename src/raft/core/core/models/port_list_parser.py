"""Parse ``spec.ports`` into validated :class:`PortSpec` tuples."""

from pathlib import Path
from typing import Any, Optional

from raft.core.core.errors.domain import DomainErrors
from .ports import PortSpec


class PortListParser:
    """Parse ``spec.ports`` into validated :class:`PortSpec` tuples."""

    def parse(self, spec: dict[str, Any], path: Path) -> tuple[PortSpec, ...]:
        self._reject_legacy_port(spec, path)
        raw = spec.get("ports")
        if raw is None or raw == []:
            return ()
        if not isinstance(raw, list):
            raise ValueError(f"{path}: spec.ports must be a list")
        ports: list[PortSpec] = []
        seen: set[str] = set()
        for index, entry in enumerate(raw):
            ports.append(self._parse_entry(entry, index=index, path=path, seen=seen))
        return tuple(ports)

    @staticmethod
    def _reject_legacy_port(spec: dict[str, Any], path: Path) -> None:
        if "port" in spec:
            raise ValueError(f"{path}: spec.port is not supported; use spec.ports[]")

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
            container_port=DomainErrors.require_int(
                entry["containerPort"],
                label=f"spec.ports[{name!r}].containerPort",
                path=path,
            ),
            expose=str(entry.get("expose", "http")).strip().lower() or "http",
            public_port=self._public_port(entry, name=name, path=path),
            protocol=str(entry.get("protocol", "tcp")).strip().lower() or "tcp",
            proxy_protocol=DomainErrors.require_bool(
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
        return DomainErrors.require_int(public_raw, label=f"spec.ports[{name!r}].publicPort", path=path)
