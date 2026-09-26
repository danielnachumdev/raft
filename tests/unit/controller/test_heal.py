"""Controller heal loop (Compose restart + escalate to redeploy)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.config.paths import ensure_raft_home
from raft.config.settings_types import HealingConfig
from raft.controller.heal import Healer, needs_heal, run_heal_forever
from raft.errors import OperatorError

from ..base import write_applied_app


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


class TestHealer:
    @staticmethod
    def _unhealthy_setup(tmp_path: Path, cfg: HealingConfig, *, deploy=None):
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web")
        docker = MagicMock()
        docker.service_runtime.return_value = ("running", "unhealthy")
        healer = Healer(home, cfg, docker, deploy=deploy)
        return healer, docker, deploy

    @staticmethod
    def _patch_locks():
        return patch("raft.controller.heal.app_and_stack_locks")

    @staticmethod
    def _enter_locks(locks) -> None:
        locks.return_value.__enter__ = MagicMock(return_value=None)
        locks.return_value.__exit__ = MagicMock(return_value=False)

    def test_disabled_skips(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        docker = MagicMock()
        healer = Healer(home, HealingConfig(enabled=False), docker)
        healer.tick()
        docker.service_runtime.assert_not_called()

    def test_counts_then_restarts_unhealthy(self, tmp_path: Path) -> None:
        cfg = HealingConfig(
            enabled=True, fail_threshold=2, cooldown_seconds=0, max_restarts=5
        )
        healer, docker, _ = self._unhealthy_setup(tmp_path, cfg)
        with self._patch_locks() as locks:
            self._enter_locks(locks)
            healer.tick(now=1.0)
            docker.restart_service.assert_not_called()
            healer.tick(now=2.0)
            docker.restart_service.assert_called_once_with("web")

    def test_start_when_exited(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web")
        docker = MagicMock()
        docker.service_runtime.return_value = ("exited", "none")
        cfg = HealingConfig(
            enabled=True, fail_threshold=1, cooldown_seconds=0, max_restarts=3
        )
        healer = Healer(home, cfg, docker)
        with self._patch_locks() as locks:
            self._enter_locks(locks)
            healer.tick(now=1.0)
            docker.start_service.assert_called_once_with("web")

    def test_cooldown_and_escalate_after_max(self, tmp_path: Path) -> None:
        cfg = HealingConfig(
            enabled=True,
            fail_threshold=1,
            cooldown_seconds=30,
            max_restarts=2,
            escalate_after_restarts=2,
        )
        healer, docker, deploy = self._unhealthy_setup(
            tmp_path, cfg, deploy=MagicMock()
        )
        with self._patch_locks() as locks:
            self._enter_locks(locks)
            self._run_cooldown_escalate(healer, docker, deploy)

    def _run_cooldown_escalate(self, healer, docker, deploy) -> None:
        healer.tick(now=10.0)
        assert docker.restart_service.call_count == 1
        healer.tick(now=15.0)  # cooldown
        assert docker.restart_service.call_count == 1
        healer.tick(now=50.0)  # second restart
        assert docker.restart_service.call_count == 2
        healer.tick(now=100.0)  # escalate to redeploy
        deploy.assert_called_once_with("web")
        assert healer.escalate_counts["web"] == 1
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
        healer, docker, deploy = self._unhealthy_setup(
            tmp_path, cfg, deploy=MagicMock()
        )
        with self._patch_locks() as locks:
            self._enter_locks(locks)
            healer.tick(now=1.0)
            healer.tick(now=2.0)
            assert docker.restart_service.call_count == 2
            healer.tick(now=3.0)
            deploy.assert_called_once_with("web")
            assert docker.restart_service.call_count == 2

    def test_escalate_uses_orchestrator_by_default(self, tmp_path: Path) -> None:
        cfg = HealingConfig(
            enabled=True,
            fail_threshold=1,
            cooldown_seconds=0,
            max_restarts=1,
            escalate_after_restarts=1,
        )
        healer, _, _ = self._unhealthy_setup(tmp_path, cfg)
        with self._patch_locks() as locks:
            self._enter_locks(locks)
            with patch("raft.controller.heal.Orchestrator") as orch_cls:
                orch = orch_cls.return_value
                healer.tick(now=1.0)
                healer.tick(now=2.0)
                orch.ensure_app_deployed.assert_called_once_with("web")

    def test_escalate_operator_error(self, tmp_path: Path) -> None:
        deploy = MagicMock(side_effect=OperatorError("boom", has_fix=False))
        cfg = HealingConfig(
            enabled=True,
            fail_threshold=1,
            cooldown_seconds=0,
            max_restarts=1,
            escalate_after_restarts=1,
        )
        healer, _, _ = self._unhealthy_setup(tmp_path, cfg, deploy=deploy)
        with self._patch_locks() as locks:
            self._enter_locks(locks)
            healer.tick(now=1.0)
            healer.tick(now=2.0)
        assert healer.escalate_counts.get("web", 0) == 0

    def test_clear_on_healthy(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web")
        docker = MagicMock()
        cfg = HealingConfig(enabled=True, fail_threshold=3)
        healer = Healer(home, cfg, docker)
        docker.service_runtime.return_value = ("running", "healthy")
        healer.tick(now=0.5)  # healthy with no prior fails
        healer.fail_counts["web"] = 2
        healer.tick(now=1.0)
        assert "web" not in healer.fail_counts

    def test_skips_scaled_to_zero(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web")
        from raft.controller.scaling_store import ScalingStore

        ScalingStore(home).mark_scaled_to_zero("web")
        docker = MagicMock()
        healer = Healer(home, HealingConfig(enabled=True, fail_threshold=1), docker)
        healer.tick(now=1.0)
        docker.service_runtime.assert_not_called()
        docker.start_service.assert_not_called()

    def test_ignores_non_heal_status(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web")
        docker = MagicMock()
        docker.service_runtime.return_value = ("restarting", "none")
        healer = Healer(home, HealingConfig(enabled=True, fail_threshold=1), docker)
        healer.tick(now=1.0)
        docker.restart_service.assert_not_called()
        docker.start_service.assert_not_called()

    def test_restart_operator_error(self, tmp_path: Path) -> None:
        cfg = HealingConfig(enabled=True, fail_threshold=1, cooldown_seconds=0)
        healer, docker, _ = self._unhealthy_setup(tmp_path, cfg)
        docker.restart_service.side_effect = OperatorError("boom", has_fix=False)
        with self._patch_locks() as locks:
            self._enter_locks(locks)
            healer.tick(now=1.0)
        assert healer.restart_counts.get("web", 0) == 0

    def test_run_heal_forever_one_iteration(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        docker = MagicMock()
        calls = {"n": 0}

        def sleep(_s: float) -> None:
            calls["n"] += 1
            if calls["n"] >= 1:
                raise StopIteration

        with pytest.raises(StopIteration):
            run_heal_forever(
                home,
                HealingConfig(enabled=False, interval_seconds=0.01),
                docker,
                sleep_fn=sleep,
            )

    def test_run_heal_forever_swallows_tick_errors(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        docker = MagicMock()
        calls = {"n": 0}

        def sleep(_s: float) -> None:
            calls["n"] += 1
            if calls["n"] >= 1:
                raise StopIteration

        with patch.object(Healer, "tick", side_effect=RuntimeError("tick boom")):
            with pytest.raises(StopIteration):
                run_heal_forever(
                    home,
                    HealingConfig(enabled=True, interval_seconds=0.01),
                    docker,
                    sleep_fn=sleep,
                )
