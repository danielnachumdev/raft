"""Scaler wake: Host-through-nginx gate before mark_awake."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from raft.models.scaling_spec import ScalingSpec

from .test_scale import TestScaler


class TestScalerWakeNginx(TestScaler):
    def test_wake_now_restarts_when_not_scaled_but_down(self, tmp_path: Path) -> None:
        scaler, docker = self._scaler(tmp_path)
        docker.service_runtime.side_effect = [
            ("exited", "none"),
            ("exited", "none"),
            ("running", "healthy"),
        ]
        docker.router_can_fetch.return_value = True
        docker.router_serves_host.return_value = True
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is True
        docker.start_service.assert_called_once_with(self.APP)
        assert not scaler.store.is_scaled_to_zero(self.APP)

    def test_wait_wake_idle_times_out(self, tmp_path: Path) -> None:
        scaler, _ = self._scaler(tmp_path)
        clock = {"t": 0.0}
        scaler._clock = lambda: clock["t"]
        scaler._sleep = lambda s: clock.__setitem__("t", clock["t"] + s)
        scaler._waking.add(self.APP)
        try:
            scaler.wait_wake_idle(timeout=0.5)
            raise AssertionError("expected TimeoutError")
        except TimeoutError:
            pass

    def test_chain_running_false_when_wake_chain_missing(self, tmp_path: Path) -> None:
        scaler, _ = self._scaler(tmp_path)
        with patch.object(scaler._deps, "wake_chain", return_value=None):
            assert scaler._chain_running(self.APP) is False

    def test_chain_running_false_when_dep_compose_missing(self, tmp_path: Path) -> None:
        scaler, _ = self._scaler(tmp_path)
        with patch.object(scaler._deps, "wake_chain", return_value=("api", self.APP)):
            with patch.object(scaler, "_compose_id", side_effect=[None]):
                assert scaler._chain_running(self.APP) is False

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

    def test_idle_stop_parks_upstream_wake_restores(self, tmp_path: Path) -> None:
        from raft.adapters.nginx import NginxUpstreamText

        scaler, docker, up = self._scaler_with_upstream(tmp_path)
        docker.service_runtime.return_value = ("running", "healthy")
        scaler.store.touch_activity(self.APP, now=0.0)
        with self.with_scale_locks():
            scaler.tick(now=20.0)
        assert NginxUpstreamText.ABSENT_HOSTNAME in up.read_text(encoding="utf-8")
        self._wake_ok(scaler, docker)
        assert f"server {self.APP}:80" in up.read_text(encoding="utf-8")

    def _scaler_with_upstream(self, tmp_path: Path):
        from raft.models.ports import PortSpec
        from raft.models.stack import load_stack

        scaler, docker = self._scaler(tmp_path)
        stack = load_stack(scaler.home)
        port = PortSpec(name="http", container_port=80, expose="http")
        up = stack.upstream_file(stack.apps[0], port)
        up.parent.mkdir(parents=True, exist_ok=True)
        up.write_text(f"server {self.APP}:80;\n", encoding="utf-8")
        return scaler, docker, up

    def _wake_ok(self, scaler, docker) -> None:
        docker.service_runtime.return_value = ("running", "none")
        docker.router_can_fetch.return_value = True
        docker.router_serves_host.return_value = True
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is True

    def test_park_restore_skips_unknown_app_names(self, tmp_path: Path) -> None:
        scaler, _docker = self._scaler(tmp_path)
        scaler._deps._park_upstreams(("ghost",))
        scaler._deps._restore_upstreams(("ghost",))
