"""SettingsSectionMeta maps RaftConfig to UI enablement descriptors."""

from __future__ import annotations

from raft.core.core.config.settings import SettingsLoader, SettingsSectionMeta
from raft.core.core.config.settings.types import HealingConfig, RaftConfig

from tests.unit.base import RaftTestCase


class TestSettingsSectionMeta(RaftTestCase):
    def test_defaults_include_all_keys(self) -> None:
        cfg = SettingsLoader().from_raw(None)
        rows = SettingsSectionMeta().for_config(cfg)
        keys = [row["key"] for row in rows]
        assert keys == [
            "logging",
            "edge",
            "healing",
            "metrics",
            "serviceLogs",
            "acme",
            "github",
            "notifications",
            "alerts",
            "dashboard",
        ]

    def test_flag_and_derived_reflect_config(self) -> None:
        base = SettingsLoader().from_raw(None)
        cfg = RaftConfig(
            logging=base.logging,
            edge=base.edge,
            healing=HealingConfig(enabled=True),
            metrics=base.metrics,
            service_logs=base.service_logs,
            acme=base.acme,
            github=base.github,
            notifications=base.notifications,
            acl=base.acl,
            alerts=base.alerts,
            dashboard=base.dashboard,
        )
        by_key = {r["key"]: r for r in SettingsSectionMeta().for_config(cfg)}
        assert by_key["healing"]["kind"] == "flag"
        assert by_key["healing"]["enabled"] is True
        assert by_key["logging"]["kind"] == "always"
        assert by_key["acme"]["enabled"] is False
        assert by_key["metrics"]["kind"] == "always"
