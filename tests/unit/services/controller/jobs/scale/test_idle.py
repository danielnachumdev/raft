"""Scaler idle-stop + activity recording."""

from pathlib import Path

from raft.core.core.errors.cta import OperatorError

from tests.unit.services.controller.jobs.scale.base import ScalerTestCase


class TestScalerIdle(ScalerTestCase):
    def test_idle_stop_when_past_idle(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        docker.service_runtime.return_value = ("running", "healthy")
        scaler.store.touch_activity(self.APP, now=0.0)
        with self.with_scale_locks():
            scaler.tick(now=20.0)
        docker.stop_service.assert_called_once_with(self.APP)
        assert scaler.store.is_scaled_to_zero(self.APP)

    def test_min_up_blocks_idle_stop(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        docker.service_runtime.return_value = ("running", "healthy")
        scaler.store.mark_awake(self.APP, min_up_seconds=100, now=0.0)
        scaler.store.touch_activity(self.APP, now=0.0)
        scaler.tick(now=50.0)
        docker.stop_service.assert_not_called()

    def test_record_activity_and_skip_no_scaling(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path, with_scaling=False)
        scaler.tick(now=1.0)
        docker.service_runtime.assert_not_called()
        scaler._clock = lambda: 42.0
        scaler.record_activity(self.APP)
        assert scaler.store.load(self.APP).last_activity_at == 42.0

    def test_late_activity_blocks_fake_idle_tick(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        docker.service_runtime.return_value = ("running", "healthy")
        scaler.store.touch_activity(self.APP, now=0.0)
        scaler._clock = lambda: 10_000.0
        scaler.record_activity(self.APP)
        with self.with_scale_locks():
            scaler.tick(now=20.0)
        docker.stop_service.assert_not_called()
        assert not scaler.store.is_scaled_to_zero(self.APP)

    def test_idle_seeds_activity_and_skips_stopped(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        docker.service_runtime.return_value = ("exited", "none")
        scaler.tick(now=1.0)
        docker.stop_service.assert_not_called()
        docker.service_runtime.return_value = ("running", "healthy")
        scaler.tick(now=2.0)
        assert scaler.store.load(self.APP).last_activity_at == 2.0

    def test_scaled_idle_branches(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        docker.service_runtime.return_value = ("running", "healthy")
        scaler.store.mark_scaled_to_zero(self.APP)
        scaler.tick(now=1.0)
        scaler.store.touch_activity(self.APP, now=0.0)
        scaler.store.mark_awake(self.APP, min_up_seconds=1, now=0.0)
        scaler.tick(now=5.0)
        docker.stop_service.assert_not_called()

    def test_idle_operator_error_swallowed(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        docker.stop_service.side_effect = OperatorError("boom", has_fix=False)
        scaler.store.mark_awake(self.APP, min_up_seconds=1, now=0.0)
        scaler.store.touch_activity(self.APP, now=0.0)
        docker.service_runtime.return_value = ("running", "healthy")
        with self.with_scale_locks():
            scaler.tick(now=20.0)
