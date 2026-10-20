"""CLI: ``raft db migrate`` / ``raft db status``."""

from pathlib import Path
from unittest.mock import MagicMock

from raft.core.core.db import MigrateFromFilesResult
from raft.core.core.models.stack import Stack
from raft.services.cli.commands.db import DbCLI
from tests.unit.base import RaftTestCase


class TestDbCLI(RaftTestCase):
    def test_migrate_prints_ok(self, isolated_raft_data_home: Path, monkeypatch) -> None:
        service = MagicMock()
        service.migrate_from_files.return_value = MigrateFromFilesResult(
            already_done=False,
            db_path=isolated_raft_data_home / "raft.sqlite",
            settings_imported=True,
            apps_imported=1,
            firewall_rules_imported=0,
            tables=("settings",),
        )
        cli = DbCLI(Stack(root=isolated_raft_data_home, apps=()), service=service)
        said: list[str] = []
        monkeypatch.setattr(
            "raft.services.cli.commands.db.OperatorSay.say",
            lambda msg: said.append(msg),
        )
        cli.migrate()
        assert "settings=True" in said[0]
        service.migrate_from_files.assert_called_once_with(force=False)

    def test_migrate_already_done(self, isolated_raft_data_home: Path, monkeypatch) -> None:
        service = MagicMock()
        service.migrate_from_files.return_value = MigrateFromFilesResult(
            already_done=True,
            db_path=isolated_raft_data_home / "raft.sqlite",
            settings_imported=False,
            apps_imported=0,
            firewall_rules_imported=0,
            tables=("settings",),
        )
        cli = DbCLI(Stack(root=isolated_raft_data_home, apps=()), service=service)
        said: list[str] = []
        monkeypatch.setattr(
            "raft.services.cli.commands.db.OperatorSay.say",
            lambda msg: said.append(msg),
        )
        cli.migrate(force=True)
        assert "already complete" in said[0]

    def test_status(self, isolated_raft_data_home: Path, monkeypatch) -> None:
        service = MagicMock()
        service.db_path.return_value = isolated_raft_data_home / "raft.sqlite"
        service.schema_revision.return_value = None
        cli = DbCLI(Stack(root=isolated_raft_data_home, apps=()), service=service)
        lines: list[str] = []
        monkeypatch.setattr(
            "raft.services.cli.commands.db.OperatorSay.say",
            lambda msg: lines.append(msg),
        )
        cli.status()
        assert any("revision: (none" in line for line in lines)
