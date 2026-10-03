"""Prove why seed+tick idle e2e flaked — and why idle_stop_now does not.

CI fingerprint after #84/#85 merges:
  idle-stop did not mark frontend scaledToZero (last_activity=3601.0 …)

3601 == idleSeconds(3600)+1 (the fake tick ``when``). That only happens when
``_consider_idle`` sees ``last is None`` and reseeds with ``now=when``.
Patching ``record_activity`` (#84) does not stop in-flight ``store.touch_activity``
from the wake HTTP thread, nor a torn/empty load window.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock, patch

from raft.controller.scale import Scaler
from raft.models.scaling_store import AppScalingState, ScalingStore

from .base import ControllerTestCase

# Matches e2e SCALING idleSeconds+1 fingerprint from CI logs.
_TICK_WHEN = 3601.0
_WALL = 1_700_000_000.0


class TestIdleActivityRaces(ControllerTestCase):
    def test_none_last_reseeds_to_tick_when_ci_fingerprint(self, tmp_path: Path) -> None:
        scaler, docker = self._running_scaler(tmp_path)
        scaler.store.touch_activity(self.APP, now=0.0)
        with patch.object(scaler.store, "load", side_effect=self._none_then_real(scaler)):
            with self.with_scale_locks():
                scaler.tick(now=_TICK_WHEN)
        state = scaler.store.load(self.APP)
        assert state.last_activity_at == _TICK_WHEN
        assert not state.scaled_to_zero
        docker.stop_service.assert_not_called()

    def test_record_activity_patch_misses_inflight_store_touch(self, tmp_path: Path) -> None:
        scaler, docker = self._running_scaler(tmp_path)
        self._overwrite_seed_after_patch(scaler)
        with self.with_scale_locks():
            scaler.tick(now=_TICK_WHEN)
        state = scaler.store.load(self.APP)
        assert state.last_activity_at == _WALL
        assert not state.scaled_to_zero
        docker.stop_service.assert_not_called()

    def test_seed_tick_fails_under_store_touch_hammer(self, tmp_path: Path) -> None:
        fails = sum(1 for _ in range(12) if not self._seed_tick_survives_hammer(tmp_path))
        assert fails >= 8, f"expected flake, only failed {fails}/12"

    def test_idle_stop_now_survives_store_touch_hammer(self, tmp_path: Path) -> None:
        scaler, docker = self._running_scaler(tmp_path)
        stop = threading.Event()
        thread = threading.Thread(target=self._hammer_touch, args=(scaler, stop))
        thread.start()
        time.sleep(0.02)
        with self.with_scale_locks():
            scaler.idle_stop_now(self.APP)
        stop.set()
        thread.join(timeout=2)
        assert scaler.store.is_scaled_to_zero(self.APP)
        docker.stop_service.assert_called()

    def test_idle_stop_now_noop_when_unknown_app(self, tmp_path: Path) -> None:
        scaler, docker = self._running_scaler(tmp_path)
        with self.with_scale_locks():
            scaler.idle_stop_now("missing-app")
        docker.stop_service.assert_not_called()

    def test_concurrent_saves_never_load_as_none(self, tmp_path: Path) -> None:
        store = ScalingStore(self.raft_home(tmp_path))
        store.touch_activity(self.APP, now=0.0)
        seen = self._race_reads_during_writes(store)
        assert seen and all(v is not None for v in seen)

    def _overwrite_seed_after_patch(self, scaler: Scaler) -> None:
        ready = threading.Event()
        done = threading.Event()

        def inflight() -> None:
            ready.wait(timeout=2)
            scaler.store.touch_activity(self.APP, now=_WALL)
            done.set()

        thread = threading.Thread(target=inflight)
        thread.start()
        with patch.object(scaler, "record_activity"):
            scaler.store.touch_activity(self.APP, now=0.0)
            ready.set()
            assert done.wait(timeout=2)
        thread.join(timeout=2)

    def _none_then_real(self, scaler: Scaler):
        real_load = scaler.store.load
        n = {"i": 0}

        def flaky_load(name: str) -> AppScalingState:
            n["i"] += 1
            if n["i"] == 1:
                return AppScalingState()
            return real_load(name)

        return flaky_load

    def _seed_tick_survives_hammer(self, tmp_path: Path) -> bool:
        scaler, _docker = self._running_scaler(tmp_path)
        stop = threading.Event()
        thread = threading.Thread(target=self._hammer_touch, args=(scaler, stop))
        thread.start()
        time.sleep(0.01)
        with patch.object(scaler, "record_activity"):
            scaler.store.touch_activity(self.APP, now=0.0)
            time.sleep(0.01)
            with self.with_scale_locks():
                scaler.tick(now=_TICK_WHEN)
        stop.set()
        thread.join(timeout=2)
        return scaler.store.is_scaled_to_zero(self.APP)

    def _hammer_touch(self, scaler: Scaler, stop: threading.Event) -> None:
        while not stop.is_set():
            scaler.store.touch_activity(self.APP, now=time.time())

    def _race_reads_during_writes(self, store: ScalingStore) -> List[Optional[float]]:
        seen: List[Optional[float]] = []
        stop = threading.Event()

        def reader() -> None:
            while not stop.is_set():
                seen.append(store.load(self.APP).last_activity_at)

        def writer() -> None:
            for i in range(200):
                store.touch_activity(self.APP, now=float(i))

        threads = [threading.Thread(target=reader), threading.Thread(target=writer)]
        for thread in threads:
            thread.start()
        threads[1].join(timeout=5)
        stop.set()
        threads[0].join(timeout=5)
        return seen

    def _running_scaler(self, tmp_path: Path):
        home = self.applied_home(tmp_path, extra=self.scaling_extra())
        docker = MagicMock()
        docker.service_runtime.return_value = ("running", "healthy")
        return Scaler(home, docker), docker
