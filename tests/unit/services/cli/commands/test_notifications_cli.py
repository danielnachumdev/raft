"""CLI ``raft notifications`` commands (writer + tester paths)."""

from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest
import yaml

from raft.core.observe.notify.registry import NotificationRegistry
from raft.core.observe.notify.settings_write import NotificationsSettingsWriter
from raft.core.observe.notify.tester import NotificationsTester
from raft.services.cli.commands.notifications import NotificationsCLI
from raft.services.cli.commands.notifications_output import NotificationsCliOutput
from tests.unit.base import RaftTestCase, StackMakers
from tests.unit.core.observe.notify.fakes import FakeStrategy


class TestNotificationsCLI(RaftTestCase):
    def _cli(
        self,
        registry: Optional[NotificationRegistry] = None,
        *,
        seed_webhook: bool = True,
    ) -> NotificationsCLI:
        home = Path(self.tmp_path)
        (home / "settings.yaml").write_text(
            "edge: {http: 80, https: null}\n", encoding="utf-8"
        )
        reg = registry if registry is not None else NotificationRegistry()
        if seed_webhook and not any(
            item["type_id"] == "webhook" for item in reg.catalog()
        ):
            reg.register(FakeStrategy("webhook"))
        writer = NotificationsSettingsWriter(home, registry=reg)
        tester = NotificationsTester(home, registry=reg)
        return NotificationsCLI(
            StackMakers.make_stack(home),
            registry=reg,
            writer=writer,
            tester=tester,
        )

    def _channel_file(self, name: str = "channel.yaml") -> Path:
        path = Path(self.tmp_path) / name
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

    def _quiet(self):
        return patch(
            "raft.services.cli.commands.notifications_output.OperatorSay.say"
        )

    def test_create_list_show_redacts(self) -> None:
        cli = self._cli()
        with self._quiet() as say:
            cli.create(str(self._channel_file()))
            cli.list()
            cli.list(json=True)
            cli.show("ops-webhook")
            cli.show("ops-webhook", json=True)
        dumped = " ".join(str(c) for c in say.call_args_list)
        assert "ops-webhook" in dumped
        assert "clear-secret" not in dumped

    def test_update_enable_disable_delete(self) -> None:
        cli = self._cli()
        patch_path = Path(self.tmp_path) / "patch.yaml"
        patch_path.write_text(
            yaml.safe_dump({"enabled": False}), encoding="utf-8"
        )
        with self._quiet():
            cli.create(str(self._channel_file()))
            cli.update("ops-webhook", str(patch_path))
            cli.enable("ops-webhook")
            cli.disable("ops-webhook")
            cli.delete("ops-webhook")
        listed = NotificationsSettingsWriter(self.tmp_path).list_public()
        assert listed["channels"] == []

    def test_strategies_and_test(self) -> None:
        cli = self._cli()
        with self._quiet():
            cli.strategies()
            cli.strategies(json=True)
            cli.create(str(self._channel_file()))
            cli.test("ops-webhook")
            cli.test("ops-webhook", json=True)

    def test_missing_show_raises(self) -> None:
        cli = self._cli()
        with pytest.raises(Exception, match="not found"):
            cli.show("missing")

    def test_missing_mutators_raise(self) -> None:
        cli = self._cli()
        patch_path = Path(self.tmp_path) / "patch.yaml"
        patch_path.write_text("enabled: true\n", encoding="utf-8")
        with pytest.raises(Exception, match="not found"):
            cli.update("missing", str(patch_path))
        with pytest.raises(Exception, match="not found"):
            cli.delete("missing")
        with pytest.raises(Exception, match="not found"):
            cli.enable("missing")
        with pytest.raises(Exception, match="not found"):
            cli.test("missing")

    def test_empty_list_and_strategies(self) -> None:
        cli = self._cli(NotificationRegistry(), seed_webhook=False)
        with self._quiet() as say:
            cli.list()
            cli.strategies()
        dumped = " ".join(str(c) for c in say.call_args_list)
        assert "No notification channels" in dumped
        assert "No notification strategies" in dumped

    def test_test_failure_exits(self) -> None:
        from raft.core.observe.notify.delivery_result import DeliveryResult

        registry = NotificationRegistry()
        registry.register(
            FakeStrategy("webhook", result=DeliveryResult.failed("boom"))
        )
        cli = self._cli(registry)
        with self._quiet():
            cli.create(str(self._channel_file()))
            with pytest.raises(SystemExit) as exc:
                cli.test("ops-webhook")
        assert exc.value.code == 1

    def test_output_write_file(self) -> None:
        out = Path(self.tmp_path) / "out.yaml"
        with self._quiet():
            NotificationsCliOutput().write_file(str(out), "id: ops\n")
        assert out.read_text(encoding="utf-8") == "id: ops\n"
