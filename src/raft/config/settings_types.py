"""Dataclasses for ``~/.raft/settings.yaml``."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Optional

from .paths import LOGS_DIRNAME, SETTINGS_FILENAME

CONFIG_FILENAME = SETTINGS_FILENAME
STREAM_PROTOCOLS = frozenset({"tcp", "udp"})

# Healing / metrics controller defaults (single source of truth).
DEFAULT_HEAL_INTERVAL_SECONDS = 15.0
DEFAULT_HEAL_TIMEOUT_SECONDS = 120.0
DEFAULT_METRICS_INTERVAL_SECONDS = 60.0
DEFAULT_METRICS_TIMEOUT_SECONDS = 30.0
DEFAULT_METRICS_BATCH_SIZE = 10
DEFAULT_METRICS_FLUSH_SECONDS = 60.0
DEFAULT_METRICS_RETENTION_MAX_AGE_DAYS = 30
DEFAULT_METRICS_RETENTION_MAX_BYTES = 100 * 1024 * 1024  # 100 MiB
DEFAULT_LOGGING_RETENTION_MAX_AGE_DAYS = 30
DEFAULT_LOGGING_RETENTION_MAX_BYTES = 100 * 1024 * 1024  # 100 MiB
DEFAULT_ACME_DIRECTORY = "https://acme-v02.api.letsencrypt.org/directory"
DEFAULT_ACME_RENEW_DAYS_BEFORE_EXPIRY = 30
DEFAULT_ACME_CHALLENGE = "http-01"
DEFAULT_GITHUB_SESSION_TTL_SECONDS = 3600


@dataclass(frozen=True)
class LoggingConfig:
    dir: str = LOGS_DIRNAME
    file: str = "raft.log"
    level: str = "INFO"
    retention_max_age_days: int = DEFAULT_LOGGING_RETENTION_MAX_AGE_DAYS
    retention_max_bytes: int = DEFAULT_LOGGING_RETENTION_MAX_BYTES

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
    interval_seconds: float = DEFAULT_HEAL_INTERVAL_SECONDS
    timeout_seconds: float = DEFAULT_HEAL_TIMEOUT_SECONDS
    fail_threshold: int = 3
    cooldown_seconds: float = 60.0
    max_restarts: int = 1
    # After this many Compose restarts (or max_restarts), call ensure_app_deployed.
    escalate_after_restarts: int = 1


@dataclass(frozen=True)
class MetricsConfig:
    """Controller resource sampling (JSONL under ``state/metrics/``)."""

    interval_seconds: float = DEFAULT_METRICS_INTERVAL_SECONDS
    timeout_seconds: float = DEFAULT_METRICS_TIMEOUT_SECONDS
    batch_size: int = DEFAULT_METRICS_BATCH_SIZE
    flush_seconds: float = DEFAULT_METRICS_FLUSH_SECONDS
    retention_max_age_days: int = DEFAULT_METRICS_RETENTION_MAX_AGE_DAYS
    retention_max_bytes: int = DEFAULT_METRICS_RETENTION_MAX_BYTES


@dataclass(frozen=True)
class AcmeConfig:
    """Public ACME TLS (``tls: acme``). Email required when any such app is applied."""

    email: Optional[str] = None
    directory: str = DEFAULT_ACME_DIRECTORY
    renew_days_before_expiry: int = DEFAULT_ACME_RENEW_DAYS_BEFORE_EXPIRY
    challenge: str = DEFAULT_ACME_CHALLENGE


@dataclass(frozen=True)
class GithubServeConfig:
    """Temporary GitHub OAuth for ``raft serve`` deploy assist (v1)."""

    mock: bool = False
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    session_ttl_seconds: int = DEFAULT_GITHUB_SESSION_TTL_SECONDS


@dataclass(frozen=True)
class NotificationChannelConfig:
    """One durable notification channel in ``settings.yaml`` ``notifications:``."""

    id: str
    type: str
    enabled: bool = True
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "settings", MappingProxyType(dict(self.settings)))


@dataclass(frozen=True)
class NotificationsConfig:
    """Outbound notification channels (framework in ``services/notify/``)."""

    enabled: bool = True
    channels: tuple[NotificationChannelConfig, ...] = ()


@dataclass(frozen=True)
class RaftConfig:
    logging: LoggingConfig = LoggingConfig()
    edge: EdgeConfig = field(default_factory=EdgeConfig)
    healing: HealingConfig = field(default_factory=HealingConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    acme: AcmeConfig = field(default_factory=AcmeConfig)
    github: GithubServeConfig = field(default_factory=GithubServeConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)


def default_config() -> RaftConfig:
    return RaftConfig()
