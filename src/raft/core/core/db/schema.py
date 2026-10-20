"""Run Alembic upgrades against a data-home SQLite file."""

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config

from .engine import DbEngine
from .path import DbPath

_ALEMBIC_DIR = Path(__file__).resolve().parent / "alembic"


class SchemaUpgrade:
    """Apply packaged Alembic revisions to ``raft.sqlite``."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self._home = home
        self._path = DbPath(home)

    def upgrade_head(self) -> Path:
        engine = DbEngine(self._home)
        db_path = engine.path()
        engine.create()
        command.upgrade(self._config(db_path), "head")
        return db_path

    def current_revision(self) -> Optional[str]:
        cfg = self._config(self._path.resolve())
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy import create_engine

        eng = create_engine(self._path.url(), future=True)
        with eng.connect() as conn:
            context = MigrationContext.configure(conn)
            return context.get_current_revision()

    def _config(self, db_path: Path) -> Config:
        cfg = Config()
        cfg.set_main_option("script_location", str(_ALEMBIC_DIR))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.resolve().as_posix()}")
        cfg.set_main_option("version_path_separator", "os")
        return cfg
