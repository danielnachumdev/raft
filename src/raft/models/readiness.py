"""App readiness: how raft decides an app (or cutover target) is live."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .ports import PortSpec

READINESS_TYPES = frozenset({"http", "tcp", "none"})


@dataclass(frozen=True)
class ReadinessSpec:
    type: str = "http"
    port: Optional[str] = None
    path: str = "/"

    def resolve_port(self, ports: tuple[PortSpec, ...]) -> Optional[PortSpec]:
        if self.type == "none":
            return None
        if self.port:
            for port in ports:
                if port.name == self.port:
                    return port
            known = ", ".join(p.name for p in ports) or "(none)"
            raise KeyError(
                f"readiness.port {self.port!r} not in ports (known: {known})"
            )
        if self.type == "http":
            for port in ports:
                if port.expose == "http":
                    return port
        if ports:
            return ports[0]
        return None


def parse_readiness(
    spec: dict[str, Any],
    ports: tuple[PortSpec, ...],
    path: Path,
) -> ReadinessSpec:
    if "readinessProbe" in spec:
        raise ValueError(
            f"{path}: readinessProbe is not supported; use spec.readiness"
        )
    raw = spec.get("readiness")
    if raw is None:
        http_ports = [p for p in ports if p.expose == "http"]
        if http_ports:
            return ReadinessSpec(type="http", port=http_ports[0].name, path="/")
        return ReadinessSpec(type="tcp", port=ports[0].name if ports else None)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: spec.readiness must be an object")
    rtype = str(raw.get("type", "http")).strip().lower() or "http"
    if rtype not in READINESS_TYPES:
        raise ValueError(
            f"{path}: readiness.type must be one of {sorted(READINESS_TYPES)}, "
            f"got {rtype!r}"
        )
    port_name = raw.get("port")
    port_s = str(port_name).strip() if port_name is not None else None
    if port_s == "":
        port_s = None
    path_raw = raw.get("path", "/")
    probe_path = str(path_raw).strip() or "/"
    if not probe_path.startswith("/"):
        probe_path = f"/{probe_path}"
    readiness = ReadinessSpec(type=rtype, port=port_s, path=probe_path)
    if rtype != "none":
        try:
            resolved = readiness.resolve_port(ports)
        except KeyError as exc:
            raise ValueError(f"{path}: {exc}") from exc
        if resolved is None:
            raise ValueError(f"{path}: readiness requires a named port")
        if rtype == "http" and resolved.expose != "http":
            raise ValueError(
                f"{path}: readiness.type=http requires an expose=http port "
                f"(got {resolved.name!r} expose={resolved.expose!r})"
            )
        if readiness.port is None:
            readiness = ReadinessSpec(
                type=rtype, port=resolved.name, path=probe_path
            )
    return readiness
