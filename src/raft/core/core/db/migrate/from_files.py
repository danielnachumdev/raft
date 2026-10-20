"""One-shot files → SQLite importer (idempotent when stamp present)."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from raft.core.core.db.models.migrate_stamp import (
    MIGRATE_STAMP_ID,
    MigrateFromFilesStamp,
)
from raft.core.core.db.schema import SchemaUpgrade
from raft.core.core.db.session import DbSessionFactory
from .apps_import import AppsFileImporter
from .firewall_import import FirewallFileImporter
from .settings_import import SettingsFileImporter

CORE_TABLES = (
    "settings",
    "apps",
    "deploy_pins",
    "firewall_rules",
    "firewall_dismissed_recommendations",
)


@dataclass(frozen=True)
class MigrateFromFilesResult:
    """Outcome of a migrate-from-files attempt."""

    already_done: bool
    db_path: Path
    settings_imported: bool
    apps_imported: int
    firewall_rules_imported: int
    tables: tuple[str, ...]


class MigrateFromFiles:
    """Upgrade schema then import highest-value MOVE paths from disk."""

    def __init__(self, home: Path) -> None:
        self._home = home
        self._schema = SchemaUpgrade(home)

    def run(self, *, force: bool = False) -> MigrateFromFilesResult:
        db_path = self._schema.upgrade_head()
        sessions = DbSessionFactory(self._home)
        with sessions.begin() as session:
            if not force and self._stamp_present(session):
                return self._already(db_path)
            return self._import_all(session, db_path)

    def _import_all(self, session: Session, db_path: Path) -> MigrateFromFilesResult:
        settings_ok = SettingsFileImporter(self._home).import_into(session)
        apps_n = AppsFileImporter(self._home).import_into(session)
        rules_n = FirewallFileImporter(self._home).import_into(session)
        self._write_stamp(session)
        return MigrateFromFilesResult(
            already_done=False,
            db_path=db_path,
            settings_imported=settings_ok,
            apps_imported=apps_n,
            firewall_rules_imported=rules_n,
            tables=CORE_TABLES,
        )

    @staticmethod
    def _already(db_path: Path) -> MigrateFromFilesResult:
        return MigrateFromFilesResult(
            already_done=True,
            db_path=db_path,
            settings_imported=False,
            apps_imported=0,
            firewall_rules_imported=0,
            tables=CORE_TABLES,
        )

    @staticmethod
    def _stamp_present(session: Session) -> bool:
        return session.get(MigrateFromFilesStamp, MIGRATE_STAMP_ID) is not None

    @staticmethod
    def _write_stamp(session: Session) -> None:
        existing = session.get(MigrateFromFilesStamp, MIGRATE_STAMP_ID)
        payload = json.dumps(list(CORE_TABLES))
        if existing is None:
            session.add(
                MigrateFromFilesStamp(
                    id=MIGRATE_STAMP_ID,
                    completed_at=datetime.now(timezone.utc),
                    tables_json=payload,
                    note="foundation import: settings/apps/firewall",
                )
            )
            return
        existing.completed_at = datetime.now(timezone.utc)
        existing.tables_json = payload
