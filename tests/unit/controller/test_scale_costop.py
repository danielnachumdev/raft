"""Scaler idle co-stop via dependsOn.scaleWithParent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.config.settings_types import HealingConfig
from raft.controller.heal import Healer
from raft.controller.scale import Scaler
from raft.models.scaling_spec import ScalingSpec
from raft.models.scaling_store import ScalingStore

from ..base import write_applied_app
from .base import ControllerTestCase


class TestScalerCostop(ControllerTestCase):
    def test_idle_stop_costops_default_dep(self, tmp_path: Path) -> None:
        _home, docker, scaler = self._dep_scaler(tmp_path)
        self._run_idle_tick(scaler, docker)
        assert [c.args[0] for c in docker.stop_service.call_args_list] == [
            "api",
            self.APP,
        ]
        assert scaler.store.is_scaled_to_zero("api")
        assert scaler.store.is_scaled_to_zero(self.APP)

    def test_idle_stop_skips_scale_with_parent_false(self, tmp_path: Path) -> None:
        home, docker, scaler = self._mixed_dep_scaler(tmp_path)
        self._run_idle_tick(scaler, docker)
        assert [c.args[0] for c in docker.stop_service.call_args_list] == [
            "api",
            self.APP,
        ]
        assert scaler.store.is_scaled_to_zero("api")
        assert not scaler.store.is_scaled_to_zero("sidecar")

    def test_wake_starts_opted_out_dep(self, tmp_path: Path) -> None:
        home, docker, scaler = self._opt_out_scaler(tmp_path)
        self._wire_wake_runtime(docker)
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is True
        assert [c.args[0] for c in docker.start_service.call_args_list] == [
            "sidecar",
            self.APP,
        ]

    def test_wake_clears_costop_dep_marker(self, tmp_path: Path) -> None:
        _home, docker, scaler = self._dep_scaler(tmp_path)
        self._wire_wake_runtime(docker)
        scaler.store.mark_scaled_to_zero("api")
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is True
        assert not scaler.store.is_scaled_to_zero("api")
        assert not scaler.store.is_scaled_to_zero(self.APP)

    def test_healer_skips_costop_dep_without_scaling(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "api")
        ScalingStore(home).mark_scaled_to_zero("api")
        docker = MagicMock()
        docker.service_runtime.return_value = ("exited", "none")
        cfg = HealingConfig(enabled=True, fail_threshold=1, cooldown_seconds=0)
        with self.with_heal_locks():
            Healer(home, cfg, docker).tick(now=1.0)
        docker.start_service.assert_not_called()

    def test_idle_stop_aborts_on_depends_error(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(
            home,
            self.APP,
            extra={**self.scaling_extra(), "dependsOn": ["missing"]},
        )
        docker = MagicMock()
        scaler = Scaler(home, docker)
        self._run_idle_tick(scaler, docker)
        docker.stop_service.assert_not_called()
        assert not scaler.store.is_scaled_to_zero(self.APP)

    def test_idle_stop_marks_dep_when_compose_missing(self, tmp_path: Path) -> None:
        _home, docker, scaler = self._dep_scaler(tmp_path)
        scaler.store.touch_activity(self.APP, now=0.0)
        docker.service_runtime.return_value = ("running", "healthy")

        def compose_id(name: str):
            return None if name == "api" else self.APP

        with self.with_scale_locks(), patch.object(
            scaler._deps, "compose_id", side_effect=compose_id
        ):
            scaler.tick(now=20.0)
        docker.stop_service.assert_called_once_with(self.APP)
        assert scaler.store.is_scaled_to_zero("api")
        assert scaler.store.is_scaled_to_zero(self.APP)

    def _run_idle_tick(self, scaler: Scaler, docker: MagicMock) -> None:
        docker.service_runtime.return_value = ("running", "healthy")
        scaler.store.touch_activity(self.APP, now=0.0)
        with self.with_scale_locks():
            scaler.tick(now=20.0)

    @staticmethod
    def _wire_wake_runtime(docker: MagicMock) -> None:
        docker.service_runtime.side_effect = [
            ("exited", "none"),
            ("running", "healthy"),
            ("exited", "none"),
            ("running", "healthy"),
        ]
        docker.router_serves_host.return_value = True

    def _dep_scaler(self, tmp_path: Path):
        home = self.raft_home(tmp_path)
        write_applied_app(home, "api")
        write_applied_app(
            home,
            self.APP,
            extra={**self.scaling_extra(), "dependsOn": ["api"]},
        )
        docker = MagicMock()
        return home, docker, Scaler(home, docker)

    def _mixed_dep_scaler(self, tmp_path: Path):
        home = self.raft_home(tmp_path)
        write_applied_app(home, "api")
        write_applied_app(home, "sidecar")
        write_applied_app(
            home,
            self.APP,
            extra={
                **self.scaling_extra(),
                "dependsOn": [
                    "api",
                    {"name": "sidecar", "scaleWithParent": False},
                ],
            },
        )
        docker = MagicMock()
        return home, docker, Scaler(home, docker)

    def _opt_out_scaler(self, tmp_path: Path):
        home = self.raft_home(tmp_path)
        write_applied_app(home, "sidecar")
        write_applied_app(
            home,
            self.APP,
            extra={
                **self.scaling_extra(),
                "dependsOn": [{"name": "sidecar", "scaleWithParent": False}],
            },
        )
        docker = MagicMock()
        return home, docker, Scaler(home, docker)
