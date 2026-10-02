"""Scaler wake: Host-through-nginx gate before mark_awake."""

from __future__ import annotations

from pathlib import Path

from raft.models.scaling_spec import ScalingSpec

from .test_scale import TestScaler


class TestScalerWakeNginx(TestScaler):
    def test_wake_nginx_host_times_out(self, tmp_path: Path) -> None:
        scaler, docker = self._scaler(tmp_path)
        clock = {"t": 100.0}
        scaler._clock = lambda: clock["t"]
        scaler._sleep = lambda s: clock.__setitem__("t", clock["t"] + s)
        docker.service_runtime.return_value = ("running", "none")
        docker.router_can_fetch.return_value = True
        docker.router_serves_host.return_value = False
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 5, 5), now=1.0) is False
        assert docker.reload_router_nginx.call_count >= 1
        assert scaler.store.is_scaled_to_zero(self.APP)

    def test_wake_reloads_until_nginx_host_ok(self, tmp_path: Path) -> None:
        scaler, docker = self._scaler(tmp_path)
        docker.service_runtime.return_value = ("running", "none")
        docker.router_can_fetch.return_value = True
        docker.router_serves_host.side_effect = [False, True]
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is True
        assert docker.reload_router_nginx.call_count == 2
        assert not scaler.store.is_scaled_to_zero(self.APP)
