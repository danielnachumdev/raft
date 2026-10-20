"""Resolve the SQLite durable-state file under ``RAFT_DATA_HOME``."""

from pathlib import Path
from typing import Optional

from raft.core.core.config.paths.constants import DB_FILENAME
from raft.core.core.config.paths.home import RaftHome

__all__ = ["DB_FILENAME", "DbPath"]


class DbPath:
    """SQLite file lives at ``{RAFT_DATA_HOME}/raft.sqlite`` (mode ``0600``)."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self._home = home

    def home(self) -> Path:
        return self._home if self._home is not None else RaftHome().resolve()

    def resolve(self) -> Path:
        return self.home() / DB_FILENAME

    def url(self) -> str:
        path = self.resolve().resolve()
        return f"sqlite:///{path.as_posix()}"
