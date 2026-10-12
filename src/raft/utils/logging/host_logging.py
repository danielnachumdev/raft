"""Host CLI logging: structured file under ``~/.raft/logs`` with rotation."""

import logging
from pathlib import Path

from ...config.settings.types import RaftConfig
from .raft_logger import RaftLogger
from .rotating_file_handler import LogRotatingFileHandler
from .rotation_bootstrap import LogRotationBootstrap
from .trace_id_filter import TraceIdFilter

_FILE_FORMAT = "%(asctime)s %(levelname)s %(tid)s [%(name)s] %(message)s"
_FILE_DATEFMT = "%Y-%m-%d %H:%M:%S"


class HostLogging:
    """Host CLI: structured file under ``~/.raft/logs`` with rotation."""

    def configure(self, data_home: Path, config: RaftConfig) -> Path:
        log_cfg = config.logging
        log_dir = log_cfg.resolve_dir(data_home)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_cfg.resolve_file(data_home)
        level = getattr(logging, log_cfg.level.upper(), logging.INFO)
        LogRotationBootstrap(
            max_age_days=log_cfg.retention_max_age_days,
            max_bytes=log_cfg.retention_max_bytes,
        ).prepare(log_file)
        root = self._attach_file_handler(log_file, level, log_cfg.retention_max_bytes)
        root.debug("logging configured file=%s level=%s", log_file, log_cfg.level)
        return log_file

    def _attach_file_handler(
        self, log_file: Path, level: int, max_bytes: int
    ) -> logging.Logger:
        root = RaftLogger().configure(level)
        handler = LogRotatingFileHandler(log_file, max_bytes=max_bytes)
        handler.setLevel(level)
        handler.addFilter(TraceIdFilter())
        handler.setFormatter(
            logging.Formatter(fmt=_FILE_FORMAT, datefmt=_FILE_DATEFMT)
        )
        root.addHandler(handler)
        return root
