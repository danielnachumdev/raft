"""Shared durable-DB capability for CLI/serve (foundation; files remain SoT)."""

from pathlib import Path
from typing import Optional

from raft.core.core.config.paths.home import RaftHome
from .migrate.from_files import MigrateFromFiles, MigrateFromFilesResult
from .path import DbPath
from .schema import SchemaUpgrade


class DurableDbService:
    """Bootstrap SQLite schema and optional migrate-from-files import."""

    def __init__(self, home: Optional[Path] = None) -> None:
        self._home = home if home is not None else RaftHome().resolve()

    @property
    def home(self) -> Path:
        return self._home

    def db_path(self) -> Path:
        return DbPath(self._home).resolve()

    def upgrade_schema(self) -> Path:
        return SchemaUpgrade(self._home).upgrade_head()

    def migrate_from_files(self, *, force: bool = False) -> MigrateFromFilesResult:
        return MigrateFromFiles(self._home).run(force=force)

    def schema_revision(self) -> Optional[str]:
        return SchemaUpgrade(self._home).current_revision()
