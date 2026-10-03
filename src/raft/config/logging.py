"""Configure stdlib logging for the raft package (file only)."""

from __future__ import annotations

import logging
from pathlib import Path

from .log_rotation import LogRotatingFileHandler, LogRotationBootstrap
from .settings import RaftConfig
from .trace_context import TraceContext

_CONFIGURED = False
_FILE_FORMAT = "%(asctime)s %(levelname)s %(tid)s [%(name)s] %(message)s"
_FILE_DATEFMT = "%Y-%m-%d %H:%M:%S"


class TraceIdFilter(logging.Filter):
    """Inject ``record.tid`` from the active :class:`TraceContext` (or ``-``)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.tid = TraceContext.current() or "-"  # type: ignore[attr-defined]
        return True


def setup_logging(data_home: Path, config: RaftConfig) -> Path:
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
    root = _configure_raft_logger(
        log_file,
        level,
        max_bytes=log_cfg.retention_max_bytes,
    )
    _CONFIGURED = True
    root.debug("logging configured file=%s level=%s", log_file, log_cfg.level)
    return log_file


def _configure_raft_logger(
    log_file: Path,
    level: int,
    *,
    max_bytes: int,
) -> logging.Logger:
    root = logging.getLogger("raft")
    root.handlers.clear()
    root.setLevel(level)
    root.propagate = False
    formatter = logging.Formatter(fmt=_FILE_FORMAT, datefmt=_FILE_DATEFMT)
    file_handler = LogRotatingFileHandler(log_file, max_bytes=max_bytes)
    file_handler.setLevel(level)
    file_handler.addFilter(TraceIdFilter())
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    return root


def reset_logging_for_tests() -> None:
    global _CONFIGURED
    root = logging.getLogger("raft")
    root.handlers.clear()
    root.propagate = True
    root.setLevel(logging.NOTSET)
    _CONFIGURED = False
