"""Dataclasses for ``~/.raft/settings.yaml``."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .paths import LOGS_DIRNAME, SETTINGS_FILENAME

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
class HealingConfig:
    """Controller self-heal (Compose restart, then escalate to redeploy)."""

    enabled: bool = False
    interval_seconds: float = 15.0
    fail_threshold: int = 3
    cooldown_seconds: float = 60.0
    max_restarts: int = 1
    # After this many Compose restarts (or max_restarts), call ensure_app_deployed.
    escalate_after_restarts: int = 1


@dataclass(frozen=True)
class RaftConfig:
    logging: LoggingConfig = LoggingConfig()
    edge: EdgeConfig = field(default_factory=EdgeConfig)
    healing: HealingConfig = field(default_factory=HealingConfig)


def default_config() -> RaftConfig:
    return RaftConfig()
