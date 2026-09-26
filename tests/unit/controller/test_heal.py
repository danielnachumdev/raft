"""Controller heal loop (Compose restart + escalate to redeploy)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.config.settings_types import HealingConfig
from raft.controller.heal import Healer, needs_heal, run_heal_forever
from raft.controller.scaling_store import ScalingStore
from raft.errors import OperatorError

from .base import ControllerTestCase


class TestNeedsHeal:
    def test_cases(self) -> None:
        assert needs_heal("exited", "none")
        assert needs_heal("dead", "none")
        assert needs_heal("missing", "none")
        assert needs_heal("running", "unhealthy")
        assert not needs_heal("running", "healthy")
        assert not needs_heal("running", "none")
        assert not needs_heal("running", "starting")
        assert not needs_heal("restarting", "none")


class TestHealer(ControllerTestCase):
    def test_disabled_skips(self, tmp_path: Path) -> None:
        docker = MagicMock()
        Healer(self.raft_home(tmp_path), HealingConfig(enabled=False), docker).tick()
        docker.service_runtime.assert_not_called()

    def test_counts_then_restarts_unhealthy(self, tmp_path: Path) -> None:
        cfg = HealingConfig(
            enabled=True, fail_threshold=2, cooldown_seconds=0, max_restarts=5
        )
        healer, docker, _ = self.unhealthy_healer(tmp_path, cfg)
        with self.with_heal_locks():
            healer.tick(now=1.0)
            docker.restart_service.assert_not_called()
            healer.tick(now=2.0)
            docker.restart_service.assert_called_once_with(self.APP)

    def test_start_when_exited(self, tmp_path: Path) -> None:
        home = self.applied_home(tmp_path)
        docker = MagicMock()
        docker.service_runtime.return_value = ("exited", "none")
        cfg = HealingConfig(
            enabled=True, fail_threshold=1, cooldown_seconds=0, max_restarts=3
        )
        with self.with_heal_locks():
            Healer(home, cfg, docker).tick(now=1.0)
            docker.start_service.assert_called_once_with(self.APP)

    def test_cooldown_and_escalate_after_max(self, tmp_path: Path) -> None:
        cfg = HealingConfig(
            enabled=True,
            fail_threshold=1,
            cooldown_seconds=30,
            max_restarts=2,
            escalate_after_restarts=2,
        )
        healer, docker, deploy = self.unhealthy_healer(
            tmp_path, cfg, deploy=MagicMock()
        )
        with self.with_heal_locks():
            self._run_cooldown_escalate(healer, docker, deploy)

    def _run_cooldown_escalate(self, healer, docker, deploy) -> None:
        healer.tick(now=10.0)
        assert docker.restart_service.call_count == 1
        healer.tick(now=15.0)  # cooldown
        assert docker.restart_service.call_count == 1
        healer.tick(now=50.0)  # second restart
        assert docker.restart_service.call_count == 2
        healer.tick(now=100.0)  # escalate to redeploy
        deploy.assert_called_once_with(self.APP)
        assert healer.escalate_counts[self.APP] == 1
        healer.tick(now=200.0)  # give up after escalate
        assert deploy.call_count == 1

    def test_escalate_after_restarts_before_max(self, tmp_path: Path) -> None:
        cfg = HealingConfig(
            enabled=True,
            fail_threshold=1,
            cooldown_seconds=0,
            max_restarts=5,
            escalate_after_restarts=2,
        )
        healer, docker, deploy = self.unhealthy_healer(
            tmp_path, cfg, deploy=MagicMock()
        )
        with self.with_heal_locks():
            healer.tick(now=1.0)
            healer.tick(now=2.0)
            assert docker.restart_service.call_count == 2
            healer.tick(now=3.0)
            deploy.assert_called_once_with(self.APP)
            assert docker.restart_service.call_count == 2

    def test_escalate_uses_orchestrator_by_default(self, tmp_path: Path) -> None:
        cfg = HealingConfig(
            enabled=True,
            fail_threshold=1,
            cooldown_seconds=0,
            max_restarts=1,
            escalate_after_restarts=1,
        )
        healer, _, _ = self.unhealthy_healer(tmp_path, cfg)
        with self.with_heal_locks():
            with patch("raft.controller.heal.Orchestrator") as orch_cls:
                orch = orch_cls.return_value
                healer.tick(now=1.0)
                healer.tick(now=2.0)
                orch.ensure_app_deployed.assert_called_once_with(self.APP)

    def test_escalate_operator_error(self, tmp_path: Path) -> None:
        deploy = MagicMock(side_effect=OperatorError("boom", has_fix=False))
        cfg = HealingConfig(
            enabled=True,
            fail_threshold=1,
            cooldown_seconds=0,
            max_restarts=1,
            escalate_after_restarts=1,
        )
        healer, _, _ = self.unhealthy_healer(tmp_path, cfg, deploy=deploy)
        with self.with_heal_locks():
            healer.tick(now=1.0)
            healer.tick(now=2.0)
        assert healer.escalate_counts.get(self.APP, 0) == 0

    def test_clear_on_healthy(self, tmp_path: Path) -> None:
        home = self.applied_home(tmp_path)
        docker = MagicMock()
        cfg = HealingConfig(enabled=True, fail_threshold=3)
        healer = Healer(home, cfg, docker)
        docker.service_runtime.return_value = ("running", "healthy")
        healer.tick(now=0.5)
        healer.fail_counts[self.APP] = 2
        healer.tick(now=1.0)
        assert self.APP not in healer.fail_counts

    def test_skips_scaled_to_zero(self, tmp_path: Path) -> None:
        home = self.applied_home(tmp_path)
        ScalingStore(home).mark_scaled_to_zero(self.APP)
        docker = MagicMock()
        Healer(home, HealingConfig(enabled=True, fail_threshold=1), docker).tick(
            now=1.0
        )
        docker.service_runtime.assert_not_called()
        docker.start_service.assert_not_called()

    def test_ignores_non_heal_status(self, tmp_path: Path) -> None:
        home = self.applied_home(tmp_path)
        docker = MagicMock()
        docker.service_runtime.return_value = ("restarting", "none")
        Healer(home, HealingConfig(enabled=True, fail_threshold=1), docker).tick(
            now=1.0
        )
        docker.restart_service.assert_not_called()
        docker.start_service.assert_not_called()

    def test_restart_operator_error(self, tmp_path: Path) -> None:
        cfg = HealingConfig(enabled=True, fail_threshold=1, cooldown_seconds=0)
        healer, docker, _ = self.unhealthy_healer(tmp_path, cfg)
        docker.restart_service.side_effect = OperatorError("boom", has_fix=False)
        with self.with_heal_locks():
            healer.tick(now=1.0)
        assert healer.restart_counts.get(self.APP, 0) == 0

    def test_run_heal_forever_one_iteration(self, tmp_path: Path) -> None:
        self._run_forever_once(tmp_path, HealingConfig(enabled=False, interval_seconds=0.01))

    def test_run_heal_forever_swallows_tick_errors(self, tmp_path: Path) -> None:
        cfg = HealingConfig(enabled=True, interval_seconds=0.01)
        with patch.object(Healer, "tick", side_effect=RuntimeError("tick boom")):
            self._run_forever_once(tmp_path, cfg)

    def _run_forever_once(self, tmp_path: Path, cfg: HealingConfig) -> None:
        home = self.raft_home(tmp_path)
        docker = MagicMock()
        calls = {"n": 0}

        def sleep(_s: float) -> None:
            calls["n"] += 1
            if calls["n"] >= 1:
                raise StopIteration

        with pytest.raises(StopIteration):
            run_heal_forever(home, cfg, docker, sleep_fn=sleep)
