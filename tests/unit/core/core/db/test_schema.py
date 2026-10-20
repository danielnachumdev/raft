"""Alembic schema upgrade tests."""

from pathlib import Path

from alembic import command

from raft.core.core.db import DurableDbService, SchemaUpgrade
from raft.core.core.db.schema import SchemaUpgrade as SchemaUpgradeCls
from tests.unit.base import RaftTestCase


class TestSchemaUpgrade(RaftTestCase):
    def test_upgrade_head_sets_revision(self, isolated_raft_data_home: Path) -> None:
        path = SchemaUpgrade(isolated_raft_data_home).upgrade_head()
        assert path.is_file()
        assert SchemaUpgrade(isolated_raft_data_home).current_revision() == "20261020_0001"

    def test_downgrade_and_reupgrade(self, isolated_raft_data_home: Path) -> None:
        schema = SchemaUpgradeCls(isolated_raft_data_home)
        db_path = schema.upgrade_head()
        cfg = schema._config(db_path)
        command.downgrade(cfg, "base")
        assert schema.current_revision() is None
        schema.upgrade_head()
        assert schema.current_revision() == "20261020_0001"

    def test_service_upgrade_and_status(self, isolated_raft_data_home: Path) -> None:
        service = DurableDbService(isolated_raft_data_home)
        assert service.home == isolated_raft_data_home
        service.upgrade_schema()
        assert service.schema_revision() == "20261020_0001"
        assert service.db_path().name == "raft.sqlite"
