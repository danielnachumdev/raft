"""Scaler idle-stop / wake record GraphEvents for chart markers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from raft.controller.scale import Scaler
from raft.errors import OperatorError
from raft.models.graph_event_store import (
    KIND_SCALING,
    SCALING_ACTION_IDLE_STOP,
    SCALING_ACTION_WAKE,
    GraphEventStore,
)
from raft.models.scaling_spec import ScalingSpec

from .base import ControllerTestCase

_EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)


class TestScaleGraphEvents(ControllerTestCase):
    def _scaler(self, tmp_path: Path, *, docker=None):
        home = self.applied_home(tmp_path, extra=self.scaling_extra())
        docker = docker or MagicMock()
        return Scaler(home, docker), docker, home

    def test_idle_stop_records_scaling_event(self, tmp_path: Path) -> None:
        scaler, docker, home = self._scaler(tmp_path)
        docker.service_runtime.return_value = ("running", "healthy")
        scaler.store.touch_activity(self.APP, now=0.0)
        with self.with_scale_locks():
            scaler.tick(now=20.0)
        events = GraphEventStore(home).events_in_window(from_ts=_EPOCH)
        assert len(events) == 1
        assert events[0].kind == KIND_SCALING
        assert events[0].service == self.APP
        assert events[0].metadata["action"] == SCALING_ACTION_IDLE_STOP
        assert events[0].metadata["app"] == self.APP

    def test_failed_idle_stop_does_not_record(self, tmp_path: Path) -> None:
        scaler, docker, home = self._scaler(tmp_path)
        docker.service_runtime.return_value = ("running", "healthy")
        docker.stop_service.side_effect = OperatorError("boom", has_fix=False)
        scaler.store.touch_activity(self.APP, now=0.0)
        with self.with_scale_locks():
            scaler.tick(now=20.0)
        assert GraphEventStore(home).events_in_window(from_ts=_EPOCH) == []

    def test_wake_records_scaling_event(self, tmp_path: Path) -> None:
        scaler, docker, home = self._scaler(tmp_path)
        docker.service_runtime.return_value = ("running", "healthy")
        docker.router_can_fetch.return_value = True
        docker.router_serves_host.return_value = True
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=10.0)
        events = GraphEventStore(home).events_in_window(from_ts=_EPOCH)
        assert len(events) == 1
        assert events[0].kind == KIND_SCALING
        assert events[0].metadata["action"] == SCALING_ACTION_WAKE
        assert events[0].label == f"Wake {self.APP}"

    def test_failed_wake_does_not_record(self, tmp_path: Path) -> None:
        scaler, docker, home = self._scaler(tmp_path)
        docker.service_runtime.return_value = ("exited", None)
        docker.start_service.side_effect = OperatorError("boom", has_fix=False)
        scaler.store.mark_scaled_to_zero(self.APP)
        with self.with_scale_locks():
            assert scaler.wake_now(self.APP, ScalingSpec(10, 30, 5), now=1.0) is False
        assert GraphEventStore(home).events_in_window(from_ts=_EPOCH) == []

    def test_wake_event_skips_unknown_compose(self, tmp_path: Path) -> None:
        scaler, _docker, home = self._scaler(tmp_path)
        scaler._record_wake_event("missing-app")
        assert GraphEventStore(home).events_in_window(from_ts=_EPOCH) == []

    def test_wake_event_oserror_does_not_raise(self, tmp_path: Path, monkeypatch) -> None:
        scaler, _docker, home = self._scaler(tmp_path)

        def boom(*_a, **_k):
            raise OSError("read-only filesystem")

        monkeypatch.setattr(GraphEventStore, "record_scaling", boom)
        scaler._record_wake_event(self.APP)
        assert GraphEventStore(home).events_in_window(from_ts=_EPOCH) == []

    def test_idle_stop_event_oserror_does_not_raise(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        scaler, docker, home = self._scaler(tmp_path)
        docker.service_runtime.return_value = ("running", "healthy")
        scaler.store.touch_activity(self.APP, now=0.0)

        def boom(*_a, **_k):
            raise OSError("read-only filesystem")

        monkeypatch.setattr(GraphEventStore, "record_scaling", boom)
        with self.with_scale_locks():
            scaler.tick(now=20.0)
        assert GraphEventStore(home).events_in_window(from_ts=_EPOCH) == []
        docker.stop_service.assert_called()
