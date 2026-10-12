"""Scaler wake paths (dependsOn, timeout, threads)."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.controller.jobs.scale import Scaler
from raft.errors.cta import OperatorError
from raft.models.scaling_spec import ScalingSpec

from ....base import write_applied_app
from .base import ScalerTestCase


class TestScalerWake(ScalerTestCase):
    def test_wake_starts_and_clears_zero(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        docker.service_runtime.return_value = ("running", "unhealthy")
        docker.router_can_fetch.side_effect = [False, True]
        docker.router_serves_host.return_value = True
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=10.0) is True
        docker.start_service.assert_not_called()
        docker.reload_router_nginx.assert_called_once_with()
        docker.router_serves_host.assert_called_once()
        assert not scaler.store.is_scaled_to_zero(self.APP)

    def test_wake_starts_depends_on_then_app(self, tmp_path: Path) -> None:
        _home, docker, scaler = self.dep_scaler(tmp_path)
        docker.service_runtime.side_effect = [
            ("exited", "none"),
            ("running", "healthy"),
            ("exited", "none"),
            ("running", "healthy"),
        ]
        docker.router_serves_host.return_value = True
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is True
        assert [c.args[0] for c in docker.start_service.call_args_list] == [
            "api",
            self.APP,
        ]
        docker.reload_router_nginx.assert_called_once()
        assert not scaler.store.is_scaled_to_zero(self.APP)

    def test_wake_skips_already_running_dep(self, tmp_path: Path) -> None:
        _home, docker, scaler = self.dep_scaler(tmp_path)
        docker.service_runtime.side_effect = [
            ("running", "healthy"),
            ("exited", "none"),
            ("running", "healthy"),
        ]
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is True
        docker.start_service.assert_called_once_with(self.APP)

    def test_wake_dep_start_failure_keeps_scaled(self, tmp_path: Path) -> None:
        _home, docker, scaler = self.dep_scaler(tmp_path)
        docker.service_runtime.return_value = ("exited", "none")
        docker.start_service.side_effect = OperatorError("boom", has_fix=False)
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is False
        docker.reload_router_nginx.assert_not_called()
        assert scaler.store.is_scaled_to_zero(self.APP)

    def test_wake_reload_failure_keeps_scaled(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        docker.service_runtime.side_effect = [
            ("exited", "none"),
            ("running", "healthy"),
        ]
        docker.reload_router_nginx.side_effect = OperatorError(
            "reload", has_fix=False
        )
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is False
        assert scaler.store.is_scaled_to_zero(self.APP)

    def test_wake_depends_on_error(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(
            home,
            self.APP,
            extra={**self.scaling_extra(), "dependsOn": ["missing"]},
        )
        scaler = Scaler(home, MagicMock())
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is False

    def test_wake_wait_times_out(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        clock = {"t": 100.0}
        scaler._clock = lambda: clock["t"]
        scaler._sleep = lambda s: clock.__setitem__("t", clock["t"] + s)
        docker.service_runtime.return_value = ("exited", "none")
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 5, 5), now=1.0) is False
        self._assert_fetch_timeout_keeps_scaled(scaler, docker, clock)

    def _assert_fetch_timeout_keeps_scaled(self, scaler, docker, clock) -> None:
        docker.service_runtime.return_value = ("running", "healthy")
        docker.router_can_fetch.return_value = False
        docker.reload_router_nginx.reset_mock()
        clock["t"] = 100.0
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 5, 5), now=1.0) is False
        docker.reload_router_nginx.assert_not_called()
        assert scaler.store.is_scaled_to_zero(self.APP)
        assert scaler._wake.http_fetch_targets("ghost") == ()
        assert scaler._wake.host_fetch_target("ghost") is None

    def test_wake_deadline_before_start(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        ticks = {"n": 0}

        def clock() -> float:
            ticks["n"] += 1
            return 100.0 if ticks["n"] == 1 else 999.0

        scaler._clock = clock
        docker.service_runtime.return_value = ("exited", "none")
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is False
        docker.start_service.assert_not_called()

    def test_wake_missing_compose_in_chain(self, tmp_path: Path) -> None:
        _home, docker, scaler = self.dep_scaler(tmp_path)
        docker.service_runtime.return_value = ("exited", "none")
        scaler.store.mark_scaled_to_zero(self.APP)

        def compose_id(name: str):
            return None if name == "api" else self.APP

        with self.with_scale_locks(), patch.object(
            scaler._deps, "compose_id", side_effect=compose_id
        ):
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is False

    def test_depends_edges_skips_bad_spec(self, tmp_path: Path) -> None:
        scaler, _docker = self.scaler(tmp_path)
        with patch.object(scaler._deps, "load_spec", return_value=None):
            assert scaler._deps.depends_edges() == {self.APP: ()}

    def test_request_wake_threads(self, tmp_path: Path) -> None:
        scaler, _ = self.scaler(tmp_path)
        scaler.store.mark_scaled_to_zero(self.APP)
        with patch.object(scaler, "wake_now", return_value=True) as wake:
            scaler.request_wake(self.APP)
            scaler.request_wake(self.APP)
            self._wait_called(wake)
        assert wake.called

    @staticmethod
    def _wait_called(wake) -> None:
        for _ in range(50):
            if wake.called:
                return
            time.sleep(0.01)

    def test_wake_timeout(self, tmp_path: Path) -> None:
        scaler, _ = self.scaler(tmp_path)
        scaler.store.mark_scaled_to_zero(self.APP)
        scaler.store.request_wake(self.APP, now=0.0)
        scaler.tick(now=40.0)
        assert scaler.store.load(self.APP).wake_timed_out is True
        scaler.tick(now=41.0)

    def test_wake_operator_error(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        docker.service_runtime.return_value = ("exited", "none")
        docker.start_service.side_effect = OperatorError("boom", has_fix=False)
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is False

    def test_load_spec_errors(self, tmp_path: Path) -> None:
        scaler, _ = self.scaler(tmp_path)
        path = scaler.home / "state" / "apps" / "web.yaml"
        path.write_text("not: yaml: [[", encoding="utf-8")
        assert scaler._load_spec(self.APP) is None

    def test_wake_now_already_up(self, tmp_path: Path) -> None:
        scaler, docker = self.scaler(tmp_path)
        docker.service_runtime.return_value = ("running", "healthy")
        assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5)) is True
        docker.start_service.assert_not_called()
        self._assert_wake_without_http_targets(scaler, docker)

    def _assert_wake_without_http_targets(self, scaler, docker) -> None:
        scaler.store.mark_scaled_to_zero("ghost")
        assert scaler.wake_now("ghost", ScalingSpec(10, 30, 5)) is False
        scaler.request_wake("ghost")
        scaler.request_wake(self.APP)
        scaler.wait_wake_idle(timeout=5.0)
        docker.reload_router_nginx.reset_mock()
        scaler.store.mark_scaled_to_zero(self.APP)
        docker.service_runtime.return_value = ("running", "none")
        docker.router_serves_host.return_value = True
        with self.with_scale_locks(), patch.object(
            scaler._wake, "http_fetch_targets", return_value=()
        ):
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is True
        docker.reload_router_nginx.assert_called_once_with()
        docker.router_serves_host.assert_called_once_with(
            f"{self.APP}.test", path="/"
        )

    def test_wake_thread_from_tick_and_busy(self, tmp_path: Path) -> None:
        scaler, _ = self.scaler(tmp_path)
        scaler.store.mark_scaled_to_zero(self.APP)
        scaler.store.request_wake(self.APP, now=0.0)
        with patch.object(scaler, "_start_wake_thread") as start:
            scaler.tick(now=1.0)
            start.assert_called_once()
        scaler._waking.add(self.APP)
        scaler._start_wake_thread(self.APP, ScalingSpec(10, 30, 5))
        assert self.APP in scaler._waking
