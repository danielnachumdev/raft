"""Operator settings — ``~/.raft/settings.yaml`` (not service inventory)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from .paths import LOGS_DIRNAME, SETTINGS_FILENAME, settings_path

# Back-compat alias for imports that still say CONFIG_FILENAME.
CONFIG_FILENAME = SETTINGS_FILENAME


@dataclass(frozen=True)
class LoggingConfig:
    """Where and how raft writes the log file (never the terminal)."""

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
class RaftConfig:
    logging: LoggingConfig = LoggingConfig()


def default_config() -> RaftConfig:
    return RaftConfig()


def load_config(data_home: Path, *, path: Optional[Path] = None) -> RaftConfig:
    """Load ``settings.yaml`` from the data home (or ``path``). Missing → defaults."""
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
        )
    )
