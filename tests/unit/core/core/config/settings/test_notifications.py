"""Parse ``host/notifications.yaml`` channel documents."""

from __future__ import annotations

from pathlib import Path

import pytest

from raft.core.core.config.settings import load_config
from raft.core.core.config.settings.strategies.notifications import NotificationsSettingsParser
from raft.core.core.errors.cta import OperatorError

from tests.unit.base import RaftTestCase


class TestNotificationsSettingsParser(RaftTestCase):
    def test_defaults_empty(self) -> None:
        assert NotificationsSettingsParser().parse(None).channels == ()
        assert NotificationsSettingsParser().parse({}).channels == ()

    def test_happy_path_channels(self) -> None:
        cfg = NotificationsSettingsParser().parse(self._sample_raw())
        assert cfg.enabled is True
        assert [c.id for c in cfg.channels] == ["ops-primary", "oncall-email"]
        assert cfg.channels[1].enabled is False
        assert cfg.channels[0].settings["url"] == "https://hooks.example.invalid/raft"

    @staticmethod
    def _sample_raw() -> dict:
        return {
            "enabled": True,
            "channels": [
                {
                    "id": "ops-primary",
                    "type": "webhook",
                    "settings": {"url": "https://hooks.example.invalid/raft"},
                },
                {
                    "id": "oncall-email",
                    "enabled": False,
                    "type": "email",
                    "settings": {"to": "ops@example.com"},
                },
            ],
        }

    def test_unknown_type_persisted(self) -> None:
        cfg = NotificationsSettingsParser().parse(
            {"channels": [{"id": "x", "type": "future-backend"}]}
        )
        assert cfg.channels[0].type == "future-backend"

    def test_load_config_reads_flat_notifications_file(self) -> None:
        host = Path(self.tmp_path) / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "settings.yaml").write_text("edge: {http: 80}\n", encoding="utf-8")
        (host / "notifications.yaml").write_text(
            "channels:\n"
            "  - id: ops-primary\n"
            "    type: webhook\n"
            "    settings:\n"
            "      url: https://hooks.example.invalid/raft\n",
            encoding="utf-8",
        )
        loaded = load_config(self.tmp_path)
        assert loaded.notifications.channels[0].id == "ops-primary"

    def test_missing_settings_file_defaults(self) -> None:
        assert load_config(self.tmp_path).notifications.channels == ()

    def test_invalid_notifications_yaml_soft_fails_on_settings_load(self) -> None:
        host = Path(self.tmp_path) / "host"
        host.mkdir(parents=True, exist_ok=True)
        (host / "settings.yaml").write_text("edge: {http: 80}\n", encoding="utf-8")
        (host / "notifications.yaml").write_text(
            "channels: not-a-list\n", encoding="utf-8"
        )
        loaded = load_config(self.tmp_path)
        assert loaded.edge.http == 80
        assert loaded.notifications.channels == ()

    @pytest.mark.parametrize(
        "raw,needle",
        [
            ("true", "must be a mapping"),
            ({"channels": {}}, "must be a list"),
            ({"channels": ["x"]}, "must be a mapping"),
            ({"channels": [{"type": "webhook"}]}, "id is required"),
            ({"channels": [{"id": "a"}]}, "type is required"),
            ({"channels": [{"id": "a", "type": "webhook", "settings": []}]}, "settings"),
            (
                {
                    "channels": [
                        {"id": "dup", "type": "webhook"},
                        {"id": "dup", "type": "email"},
                    ]
                },
                "duplicate id",
            ),
        ],
    )
    def test_invalid_shapes(self, raw, needle: str) -> None:
        with pytest.raises(OperatorError, match=needle):
            NotificationsSettingsParser().parse(raw)
