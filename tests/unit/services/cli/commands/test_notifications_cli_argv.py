"""CLI argv dispatch for ``raft notifications …``."""

from pathlib import Path
from unittest.mock import patch

import yaml

from tests.unit.services.cli.base import CliTestCase


class TestNotificationsCliArgv(CliTestCase):
    def _seed_settings(self) -> None:
        (self.tmp_path / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )

    def _channel_path(self) -> Path:
        path = self.tmp_path / "channel.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "id": "ops-webhook",
                    "type": "webhook",
                    "settings": {
                        "url": "https://example.invalid/hooks/demo-api",
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    def _quiet(self):
        return patch(
            "raft.services.cli.commands.notifications_output.OperatorSay.say"
        )

    def test_strategies_list_create_show(self) -> None:
        self._seed_settings()
        path = self._channel_path()
        with self._quiet():
            assert self.run_main(["notifications", "strategies", "--json"]) == 0
            assert self.run_main(["notifications", "list"]) == 0
            assert self.run_main(["notifications", "create", "--file", str(path)]) == 0
            assert self.run_main(["notifications", "show", "ops-webhook", "--json"]) == 0

    def test_update_enable_disable_delete(self) -> None:
        self._seed_settings()
        path = self._channel_path()
        patch_path = self.tmp_path / "patch.yaml"
        patch_path.write_text(
            yaml.safe_dump({"enabled": False}), encoding="utf-8"
        )
        with self._quiet():
            assert self.run_main(["notifications", "create", "--file", str(path)]) == 0
            assert self.run_main(self._update_argv(patch_path)) == 0
            assert self.run_main(["notifications", "enable", "ops-webhook"]) == 0
            assert self.run_main(["notifications", "disable", "ops-webhook"]) == 0
            assert self.run_main(["notifications", "delete", "ops-webhook"]) == 0

    @staticmethod
    def _update_argv(patch_path: Path) -> list[str]:
        return [
            "notifications",
            "update",
            "ops-webhook",
            "--file",
            str(patch_path),
        ]
