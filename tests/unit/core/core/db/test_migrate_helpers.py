"""Coverage for migrate helpers and JSON util."""

from pathlib import Path

import yaml

from raft.core.core.db.migrate.json_util import MigrateJson
from raft.core.core.db.migrate.settings_import import SettingsFileImporter
from raft.core.core.db.session import DbSessionFactory
from raft.core.core.db import SchemaUpgrade
from tests.unit.base import RaftTestCase


class TestMigrateHelpers(RaftTestCase):
    def test_json_round_trip(self) -> None:
        text = MigrateJson.dumps({"cidr": "192.0.2.0/24", "n": 1})
        assert MigrateJson.loads(text)["cidr"] == "192.0.2.0/24"

    def test_settings_non_mapping_skipped(self, isolated_raft_data_home: Path) -> None:
        path = isolated_raft_data_home / "host" / "settings.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("- just a list\n", encoding="utf-8")
        SchemaUpgrade(isolated_raft_data_home).upgrade_head()
        with DbSessionFactory(isolated_raft_data_home).begin() as session:
            assert SettingsFileImporter(isolated_raft_data_home).import_into(session) is False

    def test_settings_empty_file(self, isolated_raft_data_home: Path) -> None:
        path = isolated_raft_data_home / "host" / "settings.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        SchemaUpgrade(isolated_raft_data_home).upgrade_head()
        with DbSessionFactory(isolated_raft_data_home).begin() as session:
            assert SettingsFileImporter(isolated_raft_data_home).import_into(session) is True

    def test_settings_missing(self, isolated_raft_data_home: Path) -> None:
        SchemaUpgrade(isolated_raft_data_home).upgrade_head()
        with DbSessionFactory(isolated_raft_data_home).begin() as session:
            assert SettingsFileImporter(isolated_raft_data_home).import_into(session) is False

    def test_settings_update_existing(self, isolated_raft_data_home: Path) -> None:
        home = isolated_raft_data_home
        path = home / "host" / "settings.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"logging": {"level": "DEBUG"}}), encoding="utf-8")
        SchemaUpgrade(home).upgrade_head()
        importer = SettingsFileImporter(home)
        with DbSessionFactory(home).begin() as session:
            assert importer.import_into(session) is True
        path.write_text(yaml.safe_dump({"logging": {"level": "INFO"}}), encoding="utf-8")
        with DbSessionFactory(home).begin() as session:
            assert importer.import_into(session) is True
