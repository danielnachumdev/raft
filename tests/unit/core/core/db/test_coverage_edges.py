"""Edge-path coverage for migrate helpers and sessions."""

from pathlib import Path
from unittest.mock import patch

import pytest

from raft.core.core.db.migrate.apps_import import AppsFileImporter
from raft.core.core.db.migrate.settings_import import SettingsFileImporter
from raft.core.core.db.models.apps import _utc_now as apps_utc_now
from raft.core.core.db.models.migrate_stamp import _utc_now as stamp_utc_now
from raft.core.core.db.models.settings import _utc_now as settings_utc_now
from raft.core.core.db.schema import SchemaUpgrade
from raft.core.core.db.session import DbSessionFactory
from tests.unit.base import RaftTestCase


class TestCoverageEdges(RaftTestCase):
    def test_apps_try_parse_non_mapping(self, isolated_raft_data_home: Path) -> None:
        path = isolated_raft_data_home / "x.yaml"
        assert AppsFileImporter._try_parse(path, "- just a list\n") is None

    def test_apps_read_text_oserror(self, isolated_raft_data_home: Path) -> None:
        path = isolated_raft_data_home / "missing.yaml"
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(Path, "read_text", side_effect=OSError("boom")):
                assert AppsFileImporter._read_text(path) is None

    def test_apps_import_one_unreadable(self, isolated_raft_data_home: Path) -> None:
        SchemaUpgrade(isolated_raft_data_home).upgrade_head()
        path = isolated_raft_data_home / "services" / "demo-api" / "app.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x: 1\n", encoding="utf-8")
        importer = AppsFileImporter(isolated_raft_data_home)
        with DbSessionFactory(isolated_raft_data_home).begin() as session:
            with patch.object(importer, "_read_text", return_value=None):
                assert importer._import_one(session, path) is False

    def test_apps_upsert_updates_existing(self, isolated_raft_data_home: Path) -> None:
        home = isolated_raft_data_home
        self.write_applied_app(home, "demo-api", public_host="demo-api.test")
        SchemaUpgrade(home).upgrade_head()
        importer = AppsFileImporter(home)
        with DbSessionFactory(home).begin() as session:
            assert importer.import_into(session) == 1
        with DbSessionFactory(home).begin() as session:
            assert importer.import_into(session) == 1

    def test_apps_upsert_pin_updates(self, isolated_raft_data_home: Path) -> None:
        home = isolated_raft_data_home
        deploy = home / "services" / "demo-api" / "deploy"
        deploy.mkdir(parents=True, exist_ok=True)
        (deploy / "demo-api.ref").write_text("one\n", encoding="utf-8")
        SchemaUpgrade(home).upgrade_head()
        importer = AppsFileImporter(home)
        with DbSessionFactory(home).begin() as session:
            importer.import_into(session)
        (deploy / "demo-api.ref").write_text("two\n", encoding="utf-8")
        with DbSessionFactory(home).begin() as session:
            importer.import_into(session)

    def test_apps_skips_non_directory_registry_entries(
        self, isolated_raft_data_home: Path
    ) -> None:
        home = isolated_raft_data_home
        registry = home / "services"
        registry.mkdir(parents=True, exist_ok=True)
        (registry / "not-an-app.txt").write_text("skip me\n", encoding="utf-8")
        self.write_applied_app(home, "demo-api", public_host="demo-api.test")
        SchemaUpgrade(home).upgrade_head()
        with DbSessionFactory(home).begin() as session:
            assert AppsFileImporter(home).import_into(session) == 1

    def test_settings_yaml_error(self, isolated_raft_data_home: Path) -> None:
        path = isolated_raft_data_home / "host" / "settings.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("logging: [\n", encoding="utf-8")
        assert SettingsFileImporter(isolated_raft_data_home)._read_mapping() is None

    def test_session_engine_and_rollback(self, isolated_raft_data_home: Path) -> None:
        SchemaUpgrade(isolated_raft_data_home).upgrade_head()
        factory = DbSessionFactory(isolated_raft_data_home)
        assert factory.engine is not None
        with pytest.raises(RuntimeError):
            with factory.begin():
                raise RuntimeError("roll me back")

    def test_utc_now_helpers(self) -> None:
        assert apps_utc_now().tzinfo is not None
        assert settings_utc_now().tzinfo is not None
        assert stamp_utc_now().tzinfo is not None

    def test_service_default_home(self, isolated_raft_data_home: Path) -> None:
        from raft.core.core.db import DurableDbService

        service = DurableDbService()
        assert service.home == isolated_raft_data_home

    def test_force_rewrites_existing_stamp(self, isolated_raft_data_home: Path) -> None:
        from raft.core.core.db import MigrateFromFiles

        MigrateFromFiles(isolated_raft_data_home).run()
        again = MigrateFromFiles(isolated_raft_data_home).run(force=True)
        assert again.already_done is False
