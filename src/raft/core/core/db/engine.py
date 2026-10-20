"""SQLite engine factory (WAL + busy timeout; file mode ``0600``)."""

import os
from pathlib import Path
from typing import Optional

from sqlalchemy import Engine, create_engine, event, text

from .path import DbPath

_BUSY_TIMEOUT_MS = 30_000


class DbEngine:
    """Create a process-local SQLite engine for a data home."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self._path = DbPath(home)

    def path(self) -> Path:
        return self._path.resolve()

    def create(self) -> Engine:
        db_path = self._path.resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            self._path.url(),
            future=True,
            connect_args={"check_same_thread": False},
        )
        self._attach_sqlite_pragmas(engine)
        self._touch_and_chmod(db_path)
        return engine

    @staticmethod
    def _attach_sqlite_pragmas(engine: Engine) -> None:
        @event.listens_for(engine, "connect")
        def _on_connect(dbapi_conn, _connection_record) -> None:  # noqa: ANN001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    @staticmethod
    def _touch_and_chmod(db_path: Path) -> None:
        if not db_path.is_file():
            db_path.touch()
        os.chmod(db_path, 0o600)

    @staticmethod
    def ping(engine: Engine) -> None:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
