"""ScalingStore + Scaler unit coverage."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.config.paths import ensure_raft_home
from raft.controller.scale import Scaler
from raft.controller.scaling_store import AppScalingState, ScalingStore
from raft.errors import OperatorError
from raft.models.scaling_spec import ScalingSpec

from ..base import write_applied_app


def _scaling_extra() -> dict:
    return {
        "scaling": {
            "idleSeconds": 10,
            "wakeTimeoutSeconds": 30,
            "minUpSeconds": 5,
        }
    }


class TestScalingStore:
    def test_markers_follow_scaled_state(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        store = ScalingStore(home)
        store.mark_scaled_to_zero("web")
        assert (home / "state/scaling/markers/web.zero").is_file()
        assert store.is_scaled_to_zero("web")
        store.mark_awake("web", min_up_seconds=5, now=100.0)
        assert not (home / "state/scaling/markers/web.zero").is_file()
        state = store.load("web")
        assert state.min_up_until == 105.0
        assert state.last_activity_at == 100.0

    def test_activity_ignored_when_scaled(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        store = ScalingStore(home)
        store.mark_scaled_to_zero("web")
        store.touch_activity("web", now=50.0)
        assert store.load("web").last_activity_at is None

    def test_corrupt_and_request_wake(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        store = ScalingStore(home)
        path = store.path_for("web")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not-json", encoding="utf-8")
        assert store.load("web") == AppScalingState()
        path.write_text("[]\n", encoding="utf-8")
        assert store.load("web") == AppScalingState()
        store.mark_scaled_to_zero("web")
        store.request_wake("web", now=1.0)
        assert store.load("web").wake_requested_at == 1.0
        store.request_wake("web", now=9.0)
        assert store.load("web").wake_requested_at == 1.0
        store.mark_wake_timeout("web")
        assert store.load("web").wake_timed_out is True
        assert (home / "state/scaling/markers/web.timeout").is_file()
        store.request_wake("nope")  # not scaled — no-op


class TestScaler:
    def test_idle_stop_when_past_idle(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web", extra=_scaling_extra())
        docker = MagicMock()
        docker.service_runtime.return_value = ("running", "healthy")
        scaler = Scaler(home, docker)
        scaler.store.touch_activity("web", now=0.0)
        with patch("raft.controller.scale.app_and_stack_locks") as locks:
            self._enter(locks)
            scaler.tick(now=20.0)
        docker.stop_service.assert_called_once_with("web")
        assert scaler.store.is_scaled_to_zero("web")

    def test_min_up_blocks_idle_stop(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web", extra=_scaling_extra())
        docker = MagicMock()
        docker.service_runtime.return_value = ("running", "healthy")
        scaler = Scaler(home, docker)
        scaler.store.mark_awake("web", min_up_seconds=100, now=0.0)
        scaler.store.touch_activity("web", now=0.0)
        scaler.tick(now=50.0)
        docker.stop_service.assert_not_called()

    def test_wake_starts_and_clears_zero(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web", extra=_scaling_extra())
        docker = MagicMock()
        scaler = Scaler(home, docker)
        scaler.store.mark_scaled_to_zero("web")
        scaling = ScalingSpec(10, 30, 5)
        with patch("raft.controller.scale.app_and_stack_locks") as locks:
            self._enter(locks)
            assert scaler.wake_now("web", scaling, now=10.0) is True
        docker.start_service.assert_called_once_with("web")
        assert not scaler.store.is_scaled_to_zero("web")

    def test_record_activity_and_skip_no_scaling(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web")
        docker = MagicMock()
        scaler = Scaler(home, docker)
        scaler.tick(now=1.0)
        docker.service_runtime.assert_not_called()
        scaler.record_activity("web")
        assert scaler.store.load("web").last_activity_at is not None

    def test_request_wake_threads(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web", extra=_scaling_extra())
        docker = MagicMock()
        scaler = Scaler(home, docker)
        scaler.store.mark_scaled_to_zero("web")
        with patch.object(scaler, "wake_now", return_value=True) as wake:
            scaler.request_wake("web")
            scaler.request_wake("web")
            for _ in range(50):
                if wake.called:
                    break
                import time

                time.sleep(0.01)
        assert wake.called

    def test_wake_timeout(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web", extra=_scaling_extra())
        scaler = Scaler(home, MagicMock())
        scaler.store.mark_scaled_to_zero("web")
        scaler.store.request_wake("web", now=0.0)
        scaler.tick(now=40.0)
        assert scaler.store.load("web").wake_timed_out is True
        scaler.tick(now=41.0)

    def test_wake_and_idle_operator_errors(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web", extra=_scaling_extra())
        docker = MagicMock()
        scaler = Scaler(home, docker)
        docker.start_service.side_effect = OperatorError("boom", has_fix=False)
        scaler.store.mark_scaled_to_zero("web")
        with patch("raft.controller.scale.app_and_stack_locks") as locks:
            self._enter(locks)
            assert scaler.wake_now("web", ScalingSpec(10, 30, 5), now=1.0) is False
        docker.stop_service.side_effect = OperatorError("boom", has_fix=False)
        scaler.store.mark_awake("web", min_up_seconds=1, now=0.0)
        scaler.store.touch_activity("web", now=0.0)
        docker.service_runtime.return_value = ("running", "healthy")
        with patch("raft.controller.scale.app_and_stack_locks") as locks:
            self._enter(locks)
            scaler.tick(now=20.0)

    def test_load_spec_errors(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web", extra=_scaling_extra())
        scaler = Scaler(home, MagicMock())
        path = home / "state" / "apps" / "web.yaml"
        path.write_text("not: yaml: [[", encoding="utf-8")
        assert scaler._load_spec("web") is None

    def test_idle_seeds_activity_and_skips_stopped(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web", extra=_scaling_extra())
        docker = MagicMock()
        docker.service_runtime.return_value = ("exited", "none")
        scaler = Scaler(home, docker)
        scaler.tick(now=1.0)
        docker.stop_service.assert_not_called()
        docker.service_runtime.return_value = ("running", "healthy")
        scaler.tick(now=2.0)
        assert scaler.store.load("web").last_activity_at == 2.0

    def test_wake_now_already_up(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web", extra=_scaling_extra())
        scaler = Scaler(home, MagicMock())
        assert scaler.wake_now("web", ScalingSpec(10, 30, 5)) is True
        scaler.store.mark_scaled_to_zero("ghost")
        assert scaler.wake_now("ghost", ScalingSpec(10, 30, 5)) is False
        scaler.request_wake("ghost")
        scaler.request_wake("web")  # has scaling but not scaled — still ok

    def test_scaled_idle_branches(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web", extra=_scaling_extra())
        docker = MagicMock()
        docker.service_runtime.return_value = ("running", "healthy")
        scaler = Scaler(home, docker)
        scaler.store.mark_scaled_to_zero("web")
        scaler.tick(now=1.0)  # no wake requested
        scaler.store.touch_activity("web", now=0.0)
        scaler.store.mark_awake("web", min_up_seconds=1, now=0.0)
        scaler.tick(now=5.0)  # idle not exceeded (idle=10)
        docker.stop_service.assert_not_called()

    def test_wake_thread_from_tick_and_busy(self, tmp_path: Path) -> None:
        home = ensure_raft_home(tmp_path / "home")
        write_applied_app(home, "web", extra=_scaling_extra())
        scaler = Scaler(home, MagicMock())
        scaler.store.mark_scaled_to_zero("web")
        scaler.store.request_wake("web", now=0.0)
        with patch.object(scaler, "_start_wake_thread") as start:
            scaler.tick(now=1.0)
            start.assert_called_once()
        scaler._waking.add("web")
        scaler._start_wake_thread("web", ScalingSpec(10, 30, 5))
        assert "web" in scaler._waking

    @staticmethod
    def _enter(locks) -> None:
        locks.return_value.__enter__ = MagicMock(return_value=None)
        locks.return_value.__exit__ = MagicMock(return_value=False)
