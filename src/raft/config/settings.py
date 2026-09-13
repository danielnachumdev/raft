"""Operator settings — ``~/.raft/settings.yaml`` (not service inventory)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .paths import LOGS_DIRNAME, SETTINGS_FILENAME, settings_path

CONFIG_FILENAME = SETTINGS_FILENAME
STREAM_PROTOCOLS = frozenset({"tcp", "udp"})


@dataclass(frozen=True)
class LoggingConfig:
    dir: str = LOGS_DIRNAME
    file: str = "raft.log"
    level: str = "INFO"

    def resolve_dir(self, data_home: Path) -> Path:
        override = os.environ.get("RAFT_LOG_DIR")
        if override:
            return Path(override).expanduser().resolve()
        path = Path(self.dir).expanduser()
        if path.is_absolute():
            return path.resolve()
        return (data_home / path).resolve()

    def resolve_file(self, data_home: Path) -> Path:
        return self.resolve_dir(data_home) / self.file


@dataclass(frozen=True)
class EdgeStream:
    name: str
    port: int
    protocol: str = "tcp"


@dataclass(frozen=True)
class EdgeConfig:
    http: Optional[int] = 80
    https: Optional[int] = 443
    streams: tuple[EdgeStream, ...] = ()

    def declared_stream_ports(self) -> dict[int, EdgeStream]:
        return {s.port: s for s in self.streams}

    def published_ports(self) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        if self.http is not None:
            out.append((self.http, "tcp"))
        if self.https is not None:
            out.append((self.https, "tcp"))
        for stream in self.streams:
            out.append((stream.port, stream.protocol))
        return out


@dataclass(frozen=True)
class RaftConfig:
    logging: LoggingConfig = LoggingConfig()
    edge: EdgeConfig = field(default_factory=EdgeConfig)


def default_config() -> RaftConfig:
    return RaftConfig()


def _optional_port(raw: Any, *, field_name: str) -> Optional[int]:
    if raw is None:
        return None
    port = int(raw)
    if not (1 <= port <= 65535):
        raise ValueError(f"settings.yaml edge.{field_name} out of range: {port}")
    return port


def _parse_edge(raw: Any) -> EdgeConfig:
    if raw is None:
        return EdgeConfig()
    if not isinstance(raw, dict):
        raise ValueError("settings.yaml edge must be a mapping")
    http = _optional_port(raw.get("http", 80), field_name="http")
    https = _optional_port(raw.get("https", 443), field_name="https")
    streams_raw = raw.get("streams", [])
    if streams_raw is None:
        streams_raw = []
    if not isinstance(streams_raw, list):
        raise ValueError("settings.yaml edge.streams must be a list")
    streams: list[EdgeStream] = []
    seen_names: set[str] = set()
    seen_ports: set[int] = set()
    for index, entry in enumerate(streams_raw):
        if not isinstance(entry, dict):
            raise ValueError(f"settings.yaml edge.streams[{index}] must be an object")
        name = str(entry.get("name", "")).strip()
        if not name:
            raise ValueError(f"settings.yaml edge.streams[{index}].name is required")
        if name in seen_names:
            raise ValueError(f"settings.yaml edge.streams: duplicate name {name!r}")
        seen_names.add(name)
        if "port" not in entry:
            raise ValueError(
                f"settings.yaml edge.streams[{name!r}].port is required"
            )
        port = int(entry["port"])
        if not (1 <= port <= 65535):
            raise ValueError(
                f"settings.yaml edge.streams[{name!r}].port out of range: {port}"
            )
        if port in seen_ports:
            raise ValueError(f"settings.yaml edge.streams: duplicate port {port}")
        if http is not None and port == http:
            raise ValueError(
                f"settings.yaml edge.streams[{name!r}].port {port} conflicts with edge.http"
            )
        if https is not None and port == https:
            raise ValueError(
                f"settings.yaml edge.streams[{name!r}].port {port} conflicts with edge.https"
            )
        seen_ports.add(port)
        protocol = str(entry.get("protocol", "tcp")).strip().lower() or "tcp"
        if protocol not in STREAM_PROTOCOLS:
            raise ValueError(
                f"settings.yaml edge.streams[{name!r}].protocol must be one of "
                f"{sorted(STREAM_PROTOCOLS)}, got {protocol!r}"
            )
        streams.append(EdgeStream(name=name, port=port, protocol=protocol))
    return EdgeConfig(http=http, https=https, streams=tuple(streams))


def load_config(data_home: Path, *, path: Optional[Path] = None) -> RaftConfig:
    config_path = path or settings_path(data_home)
    if not config_path.is_file():
        return default_config()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    raw = data.get("logging") or {}
    if not isinstance(raw, dict):
        raise ValueError("settings.yaml logging must be a mapping")
    level = str(raw.get("level", "INFO")).strip().upper() or "INFO"
    return RaftConfig(
        logging=LoggingConfig(
            dir=str(raw.get("dir", LOGS_DIRNAME)).strip() or LOGS_DIRNAME,
            file=str(raw.get("file", "raft.log")).strip() or "raft.log",
            level=level,
        ),
        edge=_parse_edge(data.get("edge")),
    )
