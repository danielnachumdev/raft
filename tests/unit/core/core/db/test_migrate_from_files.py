"""Migrate-from-files importer for settings, apps, firewall."""

from pathlib import Path

import yaml
from sqlalchemy import select

from raft.core.core.db import DurableDbService, MigrateFromFiles
from raft.core.core.db.models import (
    AppRow,
    DeployPinRow,
    FirewallDismissedRow,
    FirewallRuleRow,
    SettingsRow,
)
from raft.core.core.db.session import DbSessionFactory
from raft.core.core.models.firewall import FirewallDocument
from raft.core.core.models.state.firewall_dismissals import FirewallDismissalStore
from raft.core.core.models.state.firewall_store import FirewallStore
from tests.unit.base import RaftTestCase
from tests.unit.core.lifecycle.firewall.helpers import rule_dict


class TestMigrateFromFiles(RaftTestCase):
    def test_imports_core_tables(self, isolated_raft_data_home: Path) -> None:
        home = isolated_raft_data_home
        self._seed_home(home)
        result = DurableDbService(home).migrate_from_files()
        assert result.already_done is False
        assert result.settings_imported is True
        assert result.apps_imported == 1
        assert result.firewall_rules_imported == 1
        self._assert_rows(home)

    def test_idempotent_without_force(self, isolated_raft_data_home: Path) -> None:
        home = isolated_raft_data_home
        self._seed_home(home)
        first = MigrateFromFiles(home).run()
        second = MigrateFromFiles(home).run()
        assert first.already_done is False
        assert second.already_done is True

    def test_force_reimports(self, isolated_raft_data_home: Path) -> None:
        home = isolated_raft_data_home
        self._seed_home(home)
        MigrateFromFiles(home).run()
        FirewallStore(home).save(
            FirewallDocument.from_mapping(
                {"version": 1, "rules": [rule_dict("lab"), rule_dict("lab2")]},
                path="fw",
            )
        )
        result = MigrateFromFiles(home).run(force=True)
        assert result.already_done is False
        assert result.firewall_rules_imported == 2

    def test_empty_home_still_stamps(self, isolated_raft_data_home: Path) -> None:
        result = MigrateFromFiles(isolated_raft_data_home).run()
        assert result.settings_imported is False
        assert result.apps_imported == 0
        again = MigrateFromFiles(isolated_raft_data_home).run()
        assert again.already_done is True

    def test_skips_invalid_registry_yaml(self, isolated_raft_data_home: Path) -> None:
        home = isolated_raft_data_home
        bad = home / "services" / "broken" / "app.yaml"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text("not: [valid\n", encoding="utf-8")
        result = MigrateFromFiles(home).run()
        assert result.apps_imported == 0

    def _seed_home(self, home: Path) -> None:
        self.write_settings(home, {"logging": {"level": "INFO"}})
        self.write_applied_app(home, "demo-api", public_host="demo-api.test")
        deploy = home / "services" / "demo-api" / "deploy"
        deploy.mkdir(parents=True, exist_ok=True)
        (deploy / "demo-api.ref").write_text("abc123\n", encoding="utf-8")
        FirewallStore(home).save(
            FirewallDocument.from_mapping(
                {"version": 1, "rules": [rule_dict("office-443", port=443)]},
                path="fw",
            )
        )
        FirewallDismissalStore(home).dismiss("baseline-default-deny")

    def _assert_rows(self, home: Path) -> None:
        with DbSessionFactory(home).begin() as session:
            settings = session.get(SettingsRow, 1)
            assert settings is not None
            assert "logging" in settings.payload_json
            app = session.get(AppRow, "demo-api")
            assert app is not None
            assert app.source_kind == "local"
            assert "demo-api" in app.manifest_yaml
            pin = session.get(DeployPinRow, "demo-api")
            assert pin is not None
            assert pin.ref_text is not None and "abc123" in pin.ref_text
            rules = session.scalars(select(FirewallRuleRow)).all()
            assert len(rules) == 1
            assert rules[0].cidr == "192.0.2.0/24"
            dismissed = session.scalars(select(FirewallDismissedRow)).all()
            assert {row.recommendation_id for row in dismissed} == {
                "baseline-default-deny"
            }
