"""ScalingStore unit coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from raft.models.state.scaling_store import AppScalingState, ScalingStore
from raft.models.state.wake_progress import WakeProgress

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
        first_id = store.load(self.APP).wake_id
        assert first_id
        store.request_wake(self.APP, now=9.0)
        assert store.load(self.APP).wake_requested_at == 1.0
        assert store.load(self.APP).wake_id == first_id
        store.request_wake("nope")

    def test_timeout_marker_exclusive_and_retry_resets(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        store = ScalingStore(home)
        store.mark_scaled_to_zero(self.APP)
        first_id = store.request_wake(self.APP, now=1.0)
        store.mark_wake_timeout(self.APP)
        assert store.load(self.APP).wake_timed_out is True
        assert store.load(self.APP).wake_id == first_id
        assert (home / "state/scaling/markers/web.timeout").is_file()
        assert not (home / "state/scaling/markers/web.zero").is_file()
        store.request_wake(self.APP, now=50.0)
        state = store.load(self.APP)
        assert state.wake_timed_out is False
        assert state.wake_requested_at == 50.0
        assert state.wake_id and state.wake_id != first_id
        assert (home / "state/scaling/markers/web.zero").is_file()
        assert not (home / "state/scaling/markers/web.timeout").is_file()
        assert (home / "state/scaling/markers/web.id").read_text(
            encoding="utf-8"
        ) == state.wake_id

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

    def test_wake_id_mints_if_missing_and_clears_on_awake(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        store = ScalingStore(home)
        store.save(
            self.APP,
            AppScalingState(scaled_to_zero=True, wake_requested_at=1.0),
        )
        minted = store.request_wake(self.APP, now=2.0)
        assert minted
        assert store.load(self.APP).wake_requested_at == 1.0
        assert (home / "state/scaling/markers/web.id").read_text(encoding="utf-8") == minted
        store.mark_awake(self.APP, min_up_seconds=1, now=3.0)
        assert store.load(self.APP).wake_id is None
        assert not (home / "state/scaling/markers/web.id").is_file()

    def test_wake_id_blank_json_is_none(self) -> None:
        state = AppScalingState.from_mapping({"wakeId": "  "})
        assert state.wake_id is None
        assert WakeProgress.from_mapping(None) is None
        assert WakeProgress.from_mapping({"stage": "  "}) is None
        assert WakeProgress.from_mapping({"stage": "wait_host"}).log_tail() == (
            "stage=wait_host"
        )
        assert WakeProgress("wait_host").to_mapping() == {"stage": "wait_host"}
        assert WakeProgress("wait_host", service="web").to_mapping() == {
            "stage": "wait_host",
            "service": "web",
        }
        assert WakeProgress("wait_host", detail="refused").to_mapping() == {
            "stage": "wait_host",
            "detail": "refused",
        }

    def test_note_wake_progress_clears_on_awake(self, tmp_path: Path) -> None:
        store = ScalingStore(self.raft_home(tmp_path))
        store.mark_scaled_to_zero(self.APP)
        store.request_wake(self.APP)
        store.note_wake_progress(
            self.APP, "wait_fetch", service=self.APP, detail="refused"
        )
        assert store.wake_progress_log(self.APP) == (
            f"stage=wait_fetch service={self.APP} detail=refused"
        )
        store.mark_awake(self.APP, min_up_seconds=1, now=1.0)
        assert store.wake_progress_log(self.APP) == "-"

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
