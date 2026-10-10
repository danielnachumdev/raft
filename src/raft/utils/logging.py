"""Shared logging setup — host CLI (file) vs controller (stdout)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from ..config.settings_types import RaftConfig
from .log_rotation import LogRotatingFileHandler, LogRotationBootstrap
from .trace import TraceContext

__all__ = [
    "TraceIdFilter",
    "reset_logging_for_tests",
    "setup_controller_logging",
    "setup_logging",
]

_CONFIGURED = False
_FILE_FORMAT = "%(asctime)s %(levelname)s %(tid)s [%(name)s] %(message)s"
_FILE_DATEFMT = "%Y-%m-%d %H:%M:%S"
_STDOUT_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


class TraceIdFilter(logging.Filter):
    """Inject ``record.tid`` from the active :class:`TraceContext` (or ``-``)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.tid = TraceContext.current() or "-"  # type: ignore[attr-defined]
        return True


def setup_logging(data_home: Path, config: RaftConfig) -> Path:
    """Host CLI: structured file under ``~/.raft/logs`` with rotation."""
    global _CONFIGURED
    log_cfg = config.logging
    log_dir = log_cfg.resolve_dir(data_home)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_cfg.resolve_file(data_home)
    level = getattr(logging, log_cfg.level.upper(), logging.INFO)
    LogRotationBootstrap(
        max_age_days=log_cfg.retention_max_age_days,
        max_bytes=log_cfg.retention_max_bytes,
    ).prepare(log_file)
    root = _configure_file_logger(
        log_file,
        level,
        max_bytes=log_cfg.retention_max_bytes,
    )
    _CONFIGURED = True
    root.debug("logging configured file=%s level=%s", log_file, log_cfg.level)
    return log_file


def setup_controller_logging(config: RaftConfig) -> None:
    """Controller: stdout only (data home may be mounted read-only).

    Do not open ``~/.raft/logs``: the controller runs as root with a bind-mounted
    data home, and file handlers would create root-owned files the host CLI
    cannot replace.
    """
    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    root = _raft_root(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(fmt=_STDOUT_FORMAT, datefmt=_FILE_DATEFMT)
    )
    root.addHandler(handler)


def reset_logging_for_tests() -> None:
    global _CONFIGURED
    root = logging.getLogger("raft")
    root.handlers.clear()
    root.propagate = True
    root.setLevel(logging.NOTSET)
    _CONFIGURED = False


def _configure_file_logger(
    log_file: Path,
    level: int,
    *,
    max_bytes: int,
) -> logging.Logger:
    root = _raft_root(level)
    formatter = logging.Formatter(fmt=_FILE_FORMAT, datefmt=_FILE_DATEFMT)
    file_handler = LogRotatingFileHandler(log_file, max_bytes=max_bytes)
    file_handler.setLevel(level)
    file_handler.addFilter(TraceIdFilter())
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    return root


def _raft_root(level: int) -> logging.Logger:
    root = logging.getLogger("raft")
    root.handlers.clear()
    root.setLevel(level)
    root.propagate = False
    return root
