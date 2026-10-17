"""Notifier safe no-op and fan-out with registered strategies."""

from pathlib import Path
from unittest.mock import MagicMock

from raft.core.observe.notify.event import NotificationEvent
from raft.core.observe.notify.severity import NotificationSeverity
from raft.core.observe.notify.notifier import Notifier
from raft.core.observe.notify.registry import NotificationRegistry

from .fakes import FakeStrategy
from tests.unit.base import RaftTestCase


class TestNotifier(RaftTestCase):
    def test_noop_when_disabled_or_unknown_types(self) -> None:
        home = Path(self.tmp_path)
        self._write_channels(home, enabled=False)
        Notifier(home, registry=NotificationRegistry()).notify(self._event())
        self._write_channels(home, enabled=True, type_id="future-backend")
        Notifier(home).notify(self._event())

    def test_dispatches_registered_enabled_channel(self) -> None:
        home = Path(self.tmp_path)
        self._write_channels(home, enabled=True, type_id="webhook")
        fake = FakeStrategy("webhook")
        registry = NotificationRegistry()
        registry.register(fake)
        notifier = Notifier(home, registry=registry)
        assert notifier.registry is registry
        notifier.notify(self._event())
        assert len(fake.delivered) == 1

    def test_dispatch_exception_swallowed(self) -> None:
        home = Path(self.tmp_path)
        self._write_channels(home, enabled=True, type_id="webhook")
        registry = NotificationRegistry()
        registry.register(FakeStrategy("webhook"))
        dispatcher = MagicMock()
        dispatcher.dispatch.side_effect = RuntimeError("boom")
        Notifier(home, registry=registry, dispatcher=dispatcher).notify(self._event())

    def test_channel_ids_filter_and_deliver(self) -> None:
        home = Path(self.tmp_path)
        self._write_two_channels(home)
        fake = FakeStrategy("webhook")
        registry = NotificationRegistry()
        registry.register(fake)
        deliveries = Notifier(home, registry=registry).deliver(
            self._event(), channel_ids=["ops-primary", "missing"]
        )
        assert len(deliveries) == 1
        assert deliveries[0].channel_id == "ops-primary"

    @staticmethod
    def _write_two_channels(home: Path) -> None:
        (home / "settings.yaml").write_text(
            "notifications:\n  enabled: true\n  channels:\n"
            "    - id: ops-primary\n      type: webhook\n"
            "      settings: {url: https://hooks.example.invalid/x}\n"
            "    - id: ops-secondary\n      type: webhook\n"
            "      settings: {url: https://hooks.example.invalid/y}\n",
            encoding="utf-8",
        )

    def _write_channels(
        self, home: Path, *, enabled: bool, type_id: str = "webhook"
    ) -> None:
        path = home / "settings.yaml"
        flag = "true" if enabled else "false"
        path.write_text(
            "notifications:\n"
            f"  enabled: {flag}\n"
            "  channels:\n"
            "    - id: ops-primary\n"
            f"      type: {type_id}\n"
            "      settings:\n"
            "        url: https://hooks.example.invalid/x\n",
            encoding="utf-8",
        )

    @staticmethod
    def _event() -> NotificationEvent:
        return NotificationEvent(
            kind="test.kind",
            severity=NotificationSeverity.INFO,
            title="demo",
            body="demo body",
        )
