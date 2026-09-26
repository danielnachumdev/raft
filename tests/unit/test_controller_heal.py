"""Controller heal loop (Phase 1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.config.paths import ensure_raft_home
from raft.config.settings import HealingConfig
from raft.controller.heal import Healer, needs_heal, run_heal_forever
from raft.errors import OperatorError

from .base import write_applied_app


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
    def test_disabled_skips(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        docker = MagicMock()
        healer = Healer(home, HealingConfig(enabled=False), docker)
        healer.tick()
        docker.service_runtime.assert_not_called()

    def test_counts_then_restarts_unhealthy(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web")
        docker = MagicMock()
        docker.service_runtime.return_value = ("running", "unhealthy")
        cfg = HealingConfig(
            enabled=True, fail_threshold=2, cooldown_seconds=0, max_restarts=5
        )
        healer = Healer(home, cfg, docker)
        with patch("raft.controller.heal.app_and_stack_locks") as locks:
            locks.return_value.__enter__ = MagicMock(return_value=None)
            locks.return_value.__exit__ = MagicMock(return_value=False)
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
        with patch("raft.controller.heal.app_and_stack_locks") as locks:
            locks.return_value.__enter__ = MagicMock()
            locks.return_value.__exit__ = MagicMock(return_value=False)
            healer.tick(now=1.0)
            docker.start_service.assert_called_once_with("web")

    def test_cooldown_and_max_restarts(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web")
        docker = MagicMock()
        docker.service_runtime.return_value = ("running", "unhealthy")
        cfg = HealingConfig(
            enabled=True, fail_threshold=1, cooldown_seconds=30, max_restarts=2
        )
        healer = Healer(home, cfg, docker)
        with patch("raft.controller.heal.app_and_stack_locks") as locks:
            locks.return_value.__enter__ = MagicMock()
            locks.return_value.__exit__ = MagicMock(return_value=False)
            healer.tick(now=10.0)
            assert docker.restart_service.call_count == 1
            healer.tick(now=15.0)  # cooldown
            assert docker.restart_service.call_count == 1
            healer.tick(now=50.0)  # second restart
            assert docker.restart_service.call_count == 2
            healer.tick(now=100.0)  # max_restarts reached
            assert docker.restart_service.call_count == 2

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
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web")
        docker = MagicMock()
        docker.service_runtime.return_value = ("running", "unhealthy")
        docker.restart_service.side_effect = OperatorError("boom", has_fix=False)
        cfg = HealingConfig(enabled=True, fail_threshold=1, cooldown_seconds=0)
        healer = Healer(home, cfg, docker)
        with patch("raft.controller.heal.app_and_stack_locks") as locks:
            locks.return_value.__enter__ = MagicMock()
            locks.return_value.__exit__ = MagicMock(return_value=False)
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
