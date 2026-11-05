"""CLI story: mutative writes print temporary GitOps override warnings (#318)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from raft.core.core.models.stack import Stack
from raft.core.observe.notify.registry import NotificationRegistry
from raft.core.observe.notify.settings_write import NotificationsSettingsWriter
from raft.services.cli.commands.alerts import AlertsCLI
from raft.services.cli.commands.firewall import FirewallCLI
from raft.services.cli.commands.notifications import NotificationsCLI
from tests.unit.base import RaftTestCase
from tests.unit.core.lifecycle.firewall.helpers import rule_dict
from tests.unit.core.observe.notify.fakes import FakeStrategy

_ALERT_RULE = {
    "id": "demo-api-5xx-rate",
    "name": "demo-api 5xx",
    "severity": "error",
    "for": "0s",
    "cooldown": "15m",
    "condition": {
        "signal": "metrics.http",
        "select": {"target": "demo-api", "metric": "error_rate_5xx"},
        "kind": "threshold",
        "params": {
            "aggregate": "avg",
            "window": "5m",
            "op": "gt",
            "value": 0.05,
        },
    },
}


class TestGitopsCliWarnStory(RaftTestCase):
    """Operator mutates live host YAML via CLI; next Sync will wipe the change.

    Scenario:
      1) notifications create → warning names host/notifications.yaml.
      2) firewall replace → warning names host/firewall.yaml.
      3) alerts apply → warning names host/alerts.yaml.
      4) firewall tip dismiss → disable_tips guidance on host/firewall.yaml.
    """

    def test_notifications_create_warns_temporary_override(self) -> None:
        cli = self._notifications_cli()
        with self._patch_say() as say:
            cli.create(str(self._channel_file()))
        self._assert_write_warn(say, "host/notifications.yaml")

    def test_firewall_replace_warns_temporary_override(self) -> None:
        cli = self._firewall_cli()
        with self._patch_say() as say:
            cli.replace(str(self._firewall_file()))
        self._assert_write_warn(say, "host/firewall.yaml")

    def test_alerts_apply_warns_temporary_override(self) -> None:
        cli = self._alerts_cli()
        with self._patch_say() as say:
            cli.apply(str(self._alerts_file()))
        self._assert_write_warn(say, "host/alerts.yaml")

    def test_firewall_dismiss_warns_tips_are_temporary(self) -> None:
        cli = self._firewall_cli()
        with self._patch_say() as say:
            cli.dismiss("permit-port-80")
        dumped = self._say_text(say)
        assert "disable_tips: true" in dumped
        assert "host/firewall.yaml" in dumped

    def _notifications_cli(self) -> NotificationsCLI:
        home = self._host_home()
        reg = NotificationRegistry()
        reg.register(FakeStrategy("webhook"))
        writer = NotificationsSettingsWriter(home, registry=reg)
        return NotificationsCLI(
            Stack(root=home, apps=()), registry=reg, writer=writer
        )

    def _firewall_cli(self) -> FirewallCLI:
        home = self._host_home()
        (home / "host" / "firewall").mkdir(parents=True, exist_ok=True)
        return FirewallCLI(Stack(root=home, apps=()), orchestrator=MagicMock())

    def _alerts_cli(self) -> AlertsCLI:
        home = self._host_home()
        (home / "host" / "alerts").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "alerts:\n  enabled: true\n", encoding="utf-8"
        )
        (home / "host" / "notifications.yaml").write_text(
            "enabled: true\nchannels: []\n", encoding="utf-8"
        )
        return AlertsCLI(Stack(root=home, apps=()))

    def _host_home(self) -> Path:
        home = Path(self.tmp_path)
        (home / "host").mkdir(parents=True, exist_ok=True)
        (home / "host" / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        return home

    def _channel_file(self) -> Path:
        path = Path(self.tmp_path) / "channel.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "id": "ops-webhook",
                    "type": "webhook",
                    "settings": {
                        "url": "https://example.invalid/hooks/demo-api",
                        "token": "clear-secret",
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    def _firewall_file(self) -> Path:
        path = Path(self.tmp_path) / "rules.yaml"
        path.write_text(
            yaml.safe_dump({"version": 1, "rules": [rule_dict("lab")]}),
            encoding="utf-8",
        )
        return path

    def _alerts_file(self) -> Path:
        path = Path(self.tmp_path) / "rules.yaml"
        path.write_text(
            yaml.safe_dump({"version": 1, "rules": [_ALERT_RULE]}),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _patch_say():
        return patch("raft.core.core.ui.say.OperatorSay.say")

    @staticmethod
    def _say_text(say) -> str:
        return " ".join(str(c.args[0]) for c in say.call_args_list if c.args)

    def _assert_write_warn(self, say, host_path: str) -> None:
        dumped = self._say_text(say)
        assert "Temporary host override" in dumped
        assert "GitOps Sync" in dumped
        assert host_path in dumped
