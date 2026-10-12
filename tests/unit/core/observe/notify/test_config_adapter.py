"""NotifyConfigAdapter: settings → descriptors + registry validate."""

import pytest

from raft.core.core.config.settings.types import NotificationChannelConfig, NotificationsConfig
from raft.core.core.errors.cta import OperatorError
from raft.core.observe.notify.config_adapter import NotifyConfigAdapter
from raft.core.observe.notify.registry import NotificationRegistry

from .fakes import FakeStrategy
from tests.unit.base import RaftTestCase


class TestNotifyConfigAdapter(RaftTestCase):
    def test_descriptors_and_master_disable(self) -> None:
        cfg = NotificationsConfig(
            channels=(
                NotificationChannelConfig(
                    id="ops-primary",
                    type="webhook",
                    settings={"url": "https://hooks.example.invalid/x"},
                ),
            )
        )
        desc = NotifyConfigAdapter().descriptors(cfg)
        assert desc[0].channel_id == "ops-primary" and desc[0].enabled is True
        off = NotificationsConfig(enabled=False, channels=cfg.channels)
        assert NotifyConfigAdapter().descriptors(off)[0].enabled is False

    def test_validate_registered(self) -> None:
        registry = NotificationRegistry()
        registry.register(FakeStrategy("webhook"))
        cfg = NotificationsConfig(
            channels=(
                NotificationChannelConfig(id="ops-primary", type="webhook"),
                NotificationChannelConfig(id="bad", type="missing"),
            )
        )
        with pytest.raises(OperatorError, match="channel 'bad'"):
            NotifyConfigAdapter().validate_registered(cfg, registry)
        ok = NotificationsConfig(
            channels=(NotificationChannelConfig(id="ops-primary", type="webhook"),)
        )
        NotifyConfigAdapter().validate_registered(ok, registry)
