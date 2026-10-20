"""DbPath + DbEngine unit tests."""

import os
import stat
from pathlib import Path

from sqlalchemy import text

from raft.core.core.db import DB_FILENAME, DbEngine, DbPath
from tests.unit.base import RaftTestCase


class TestDbPathEngine(RaftTestCase):
    def test_path_under_data_home(self, isolated_raft_data_home: Path) -> None:
        path = DbPath(isolated_raft_data_home).resolve()
        assert path == isolated_raft_data_home / DB_FILENAME
        assert DbPath(isolated_raft_data_home).url().startswith("sqlite:///")

    def test_engine_creates_chmod_600(self, isolated_raft_data_home: Path) -> None:
        engine = DbEngine(isolated_raft_data_home).create()
        db_path = DbEngine(isolated_raft_data_home).path()
        assert db_path.is_file()
        mode = stat.S_IMODE(os.stat(db_path).st_mode)
        assert mode == 0o600
        DbEngine.ping(engine)
        with engine.connect() as conn:
            assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
