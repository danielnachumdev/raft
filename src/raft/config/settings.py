"""raft.yaml — orchestrator runtime settings (not service inventory)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

CONFIG_FILENAME = "raft.yaml"


@dataclass(frozen=True)
class LoggingConfig:
    """Where and how raft writes the log file (never the terminal)."""

    dir: str = "logs"
    file: str = "raft.log"
    level: str = "INFO"

    def resolve_dir(self, repo_root: Path) -> Path:
        override = os.environ.get("RAFT_LOG_DIR")
        if override:
            return Path(override).expanduser().resolve()
        path = Path(self.dir).expanduser()
        if path.is_absolute():
            return path.resolve()
        return (repo_root / path).resolve()

    def resolve_file(self, repo_root: Path) -> Path:
        return self.resolve_dir(repo_root) / self.file


@dataclass(frozen=True)
class RaftConfig:
    logging: LoggingConfig = LoggingConfig()


def default_config() -> RaftConfig:
    return RaftConfig()


def load_config(repo_root: Path, *, path: Optional[Path] = None) -> RaftConfig:
    """Load ``raft.yaml`` from the repo root (or ``path``). Missing file → defaults."""
    config_path = path or (repo_root / CONFIG_FILENAME)
    if not config_path.is_file():
        return default_config()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    raw = data.get("logging") or {}
    if not isinstance(raw, dict):
        raise ValueError("raft.yaml logging must be a mapping")
    level = str(raw.get("level", "INFO")).strip().upper() or "INFO"
    return RaftConfig(
        logging=LoggingConfig(
            dir=str(raw.get("dir", "logs")).strip() or "logs",
            file=str(raw.get("file", "raft.log")).strip() or "raft.log",
            level=level,
        )
    )
