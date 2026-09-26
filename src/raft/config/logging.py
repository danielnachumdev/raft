"""Configure stdlib logging for the raft package (file only)."""

import logging
from pathlib import Path

from .settings import RaftConfig

_CONFIGURED = False


def setup_logging(data_home: Path, config: RaftConfig) -> Path:
    global _CONFIGURED
    log_cfg = config.logging
    log_dir = log_cfg.resolve_dir(data_home)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_cfg.resolve_file(data_home)
    level = getattr(logging, log_cfg.level.upper(), logging.INFO)
    root = _configure_raft_logger(log_file, level)
    _CONFIGURED = True
    root.debug("logging configured file=%s level=%s", log_file, log_cfg.level)
    return log_file


def _configure_raft_logger(log_file: Path, level: int) -> logging.Logger:
    root = logging.getLogger("raft")
    root.handlers.clear()
    root.setLevel(level)
    root.propagate = False
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
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
