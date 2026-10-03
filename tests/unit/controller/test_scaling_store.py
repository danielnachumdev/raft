"""ScalingStore unit coverage."""

from __future__ import annotations

from pathlib import Path

from raft.models.scaling_store import AppScalingState, ScalingStore

from .base import ControllerTestCase


class TestScalingStore(ControllerTestCase):
    def test_markers_follow_scaled_state(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        store = ScalingStore(home)
        store.mark_scaled_to_zero(self.APP)
        assert (home / "state/scaling/markers/web.zero").is_file()
        assert store.is_scaled_to_zero(self.APP)
        store.mark_awake(self.APP, min_up_seconds=5, now=100.0)
        assert not (home / "state/scaling/markers/web.zero").is_file()
        state = store.load(self.APP)
        assert state.min_up_until == 105.0
        assert state.last_activity_at == 100.0

    def test_activity_ignored_when_scaled(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        store = ScalingStore(home)
        store.mark_scaled_to_zero(self.APP)
        store.touch_activity(self.APP, now=50.0)
        assert store.load(self.APP).last_activity_at is None

    def test_corrupt_and_request_wake(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        store = ScalingStore(home)
        path = store.path_for(self.APP)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not-json", encoding="utf-8")
        assert store.load(self.APP) == AppScalingState()
        path.write_text("[]\n", encoding="utf-8")
        assert store.load(self.APP) == AppScalingState()
        store.mark_scaled_to_zero(self.APP)
        store.request_wake(self.APP, now=1.0)
        assert store.load(self.APP).wake_requested_at == 1.0
        store.request_wake(self.APP, now=9.0)
        assert store.load(self.APP).wake_requested_at == 1.0
        store.mark_wake_timeout(self.APP)
        assert store.load(self.APP).wake_timed_out is True
        assert (home / "state/scaling/markers/web.timeout").is_file()
        store.request_wake("nope")

    def test_clear_scaled_to_zero(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        store = ScalingStore(home)
        store.clear_scaled_to_zero(self.APP)
        store.mark_scaled_to_zero(self.APP)
        store.clear_scaled_to_zero(self.APP)
        assert not store.is_scaled_to_zero(self.APP)
        assert not (home / "state/scaling/markers/web.zero").is_file()
