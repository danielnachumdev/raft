"""ScalingStore unit coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from raft.models.state.scaling_store import AppScalingState, ScalingStore

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
        store.request_wake("nope")

    def test_timeout_marker_exclusive_and_retry_resets(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        store = ScalingStore(home)
        store.mark_scaled_to_zero(self.APP)
        store.request_wake(self.APP, now=1.0)
        store.mark_wake_timeout(self.APP)
        assert store.load(self.APP).wake_timed_out is True
        assert (home / "state/scaling/markers/web.timeout").is_file()
        assert not (home / "state/scaling/markers/web.zero").is_file()
        store.request_wake(self.APP, now=50.0)
        state = store.load(self.APP)
        assert state.wake_timed_out is False
        assert state.wake_requested_at == 50.0
        assert (home / "state/scaling/markers/web.zero").is_file()
        assert not (home / "state/scaling/markers/web.timeout").is_file()

    def test_clear_scaled_to_zero(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        store = ScalingStore(home)
        store.clear_scaled_to_zero(self.APP)
        store.mark_scaled_to_zero(self.APP)
        store.clear_scaled_to_zero(self.APP)
        assert not store.is_scaled_to_zero(self.APP)
        assert not (home / "state/scaling/markers/web.zero").is_file()

    def test_save_is_atomic(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        store = ScalingStore(home)
        store.touch_activity(self.APP, now=0.0)
        path = store.path_for(self.APP)
        assert path.is_file()
        assert store.load(self.APP).last_activity_at == 0.0

    def test_public_save_round_trip(self, tmp_path: Path) -> None:
        store = ScalingStore(self.raft_home(tmp_path))
        state = AppScalingState(last_activity_at=3.0)
        store.save(self.APP, state)
        assert store.load(self.APP).last_activity_at == 3.0

    def test_atomic_write_cleans_temp_on_replace_failure(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        store = ScalingStore(home)
        store.ensure_dirs()
        path = store.path_for(self.APP)
        with patch("raft.models.state.scaling_store.os.replace", side_effect=OSError("boom")):
            with pytest.raises(OSError, match="boom"):
                store._atomic_write_json(path, {"scaledToZero": False})
        assert list(path.parent.glob(".web.json.*.tmp")) == []

    def test_atomic_write_ignores_unlink_errors(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        store = ScalingStore(home)
        store.ensure_dirs()
        path = store.path_for(self.APP)
        with patch("raft.models.state.scaling_store.os.replace", side_effect=OSError("boom")):
            with patch("raft.models.state.scaling_store.os.unlink", side_effect=OSError("gone")):
                with pytest.raises(OSError, match="boom"):
                    store._atomic_write_json(path, {"scaledToZero": False})
