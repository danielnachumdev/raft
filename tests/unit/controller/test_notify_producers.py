"""Heal escalate + scale wake timeout call Notifier."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.config.settings_types import HealingConfig
from raft.controller.heal import Healer
from raft.controller.scale import Scaler
from raft.notify.control_events import (
    KIND_HEAL_ESCALATE,
    KIND_SCALE_WAKE_TIMEOUT,
)

from .base import ControllerTestCase


class TestNotifyProducers(ControllerTestCase):
    def test_heal_escalate_notifies(self, tmp_path: Path) -> None:
        notifier = MagicMock()
        healer = self._escalate_healer(tmp_path, notifier)
        with self.with_heal_locks():
            healer.tick(now=1.0)
        event = notifier.notify.call_args[0][0]
        assert event.kind == KIND_HEAL_ESCALATE
        assert event.context["app"] == self.APP

    def _escalate_healer(self, tmp_path: Path, notifier: MagicMock) -> Healer:
        cfg = HealingConfig(
            enabled=True,
            fail_threshold=1,
            cooldown_seconds=0,
            max_restarts=1,
            escalate_after_restarts=1,
        )
        base, docker, deploy = self.unhealthy_healer(
            tmp_path, cfg, deploy=MagicMock()
        )
        healer = Healer(
            base.home, cfg, docker, deploy=deploy, notifier=notifier
        )
        healer.restart_counts[self.APP] = 1
        return healer

    def test_wake_timeout_notifies(self, tmp_path: Path) -> None:
        notifier = MagicMock()
        home = self.applied_home(tmp_path, extra=self.scaling_extra())
        scaler = Scaler(home, MagicMock(), notifier=notifier)
        scaler.store.mark_scaled_to_zero(self.APP)
        with patch.object(scaler, "_start_wake_thread"):
            scaler.request_wake(self.APP)
        wake_id = scaler.store.load(self.APP).wake_id
        state = scaler.store.load(self.APP)
        state.wake_requested_at = 0.0
        scaler.store.save(self.APP, state)
        scaler.tick(now=40.0)
        event = notifier.notify.call_args[0][0]
        assert event.kind == KIND_SCALE_WAKE_TIMEOUT
        assert event.context["id"] == wake_id
