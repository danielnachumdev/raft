"""Hosts plan: bindings from applied Apps or CLI --entry values."""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

DEFAULT_LINUX_HOSTS = Path("/etc/hosts")
DEFAULT_WINDOWS_HOSTS = Path("/mnt/c/Windows/System32/drivers/etc/hosts")
POWERSHELL = Path("/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
IPCONFIG = Path("/mnt/c/Windows/System32/ipconfig.exe")

MARKER_BEGIN = "# >>> raft hosts BEGIN"
MARKER_END = "# <<< raft hosts END"
# Older installs used hosts-manager markers; strip those too on apply/restore.
_LEGACY_MARKER_PAIRS = (("# >>> raft hosts-manager BEGIN", "# <<< raft hosts-manager END"),)
_PUBLIC_HOST_RE = re.compile(
    r'^(?:publicHost|public_host)\s*:\s*["\']?([^"\'#\s]+)["\']?\s*(?:#.*)?$'
)


def data_home() -> Path:
    override = os.environ.get("RAFT_DATA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".raft").resolve()


def public_hosts_from_registry(registry_dir: Path) -> tuple[str, ...]:
    names: list[str] = []
    for path in sorted(registry_dir.glob("*.yaml")):
        host = ""
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _PUBLIC_HOST_RE.match(line.strip())
            if match:
                host = match.group(1).strip()
                break
        if not host:
            continue
        names.append(host)
        if not host.startswith("www."):
            names.append(f"www.{host}")
    return tuple(names)


@dataclass(frozen=True)
class HostBinding:
    ip: str
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        ip = self.ip.strip()
        cleaned = tuple(n.strip() for n in self.names if n and n.strip())
        if not ip:
            raise ValueError("HostBinding.ip must be non-empty")
        if not cleaned:
            raise ValueError(f"HostBinding for {ip!r} needs at least one hostname")
        object.__setattr__(self, "ip", ip)
        object.__setattr__(self, "names", cleaned)

    def hosts_line(self) -> str:
        return f"{self.ip}\t{' '.join(self.names)}"


@dataclass(frozen=True)
class HostsPlan:
    """Declarative set of hosts lines to inject while the session is active."""

    bindings: tuple[HostBinding, ...]

    def __post_init__(self) -> None:
        if not self.bindings:
            raise ValueError("HostsPlan requires at least one HostBinding")

    @classmethod
    def from_applied_apps(cls) -> HostsPlan:
        registry = data_home() / "state" / "apps"
        names: tuple[str, ...] = ()
        if registry.is_dir():
            try:
                names = public_hosts_from_registry(registry)
            except OSError:
                names = ()
        if not names:
            raise ValueError(
                "no applied apps under ~/.raft/state/apps/*.yaml; "
                "apply an App first or pass --entry IP,hostname[,hostname...]"
            )
        return cls(bindings=(HostBinding(ip="127.0.0.1", names=names),))

    @classmethod
    def from_cli_entries(cls, values: Optional[Sequence[str]]) -> HostsPlan:
        if not values:
            return cls.from_applied_apps()

        order: list[str] = []
        merged: dict[str, list[str]] = {}
        for raw in values:
            binding = parse_cli_entry(raw)
            if binding.ip not in merged:
                order.append(binding.ip)
                merged[binding.ip] = []
            for name in binding.names:
                if name not in merged[binding.ip]:
                    merged[binding.ip].append(name)

        return cls(bindings=tuple(HostBinding(ip=ip, names=tuple(merged[ip])) for ip in order))

    def describe(self) -> list[str]:
        return [b.hosts_line() for b in self.bindings]

    def managed_block_lines(self) -> list[str]:
        return [
            MARKER_BEGIN,
            "# managed by raft hosts; do not edit",
            *(binding.hosts_line() for binding in self.bindings),
            MARKER_END,
            "",
        ]


def parse_cli_entry(raw: str) -> HostBinding:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) < 2:
        raise argparse.ArgumentTypeError(f"expected IP,name[,name...] got {raw!r}")
    ip, *names = parts
    try:
        return HostBinding(ip=ip, names=tuple(names))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


