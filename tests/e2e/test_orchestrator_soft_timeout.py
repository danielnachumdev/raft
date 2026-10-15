"""E2E: soft-timeout must not stack overlapping job workers (controller OOM root cause)."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List

import pytest

from raft.services.controller.engine.job import JobIds, JobSpec, QueuePolicy
from raft.services.controller.engine.orchestrator import JobOrchestrator
from raft.services.controller.engine.schedule import IntervalSchedule

pytestmark = pytest.mark.e2e

INTERVAL = 1.0
SOFT_TIMEOUT = 0.05
OVERLAP_CYCLES = 8


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


class _OverlapProbe:
    """Counts concurrent workers; ``peaks`` records each start's concurrency."""

    def __init__(self) -> None:
        self.hold = threading.Event()
        self.active: Dict[str, int] = {"n": 0}
        self.peaks: List[int] = []
        self._lock = threading.Lock()

    def blocking_ship(self) -> None:
        with self._lock:
            self.active["n"] += 1
            self.peaks.append(self.active["n"])
        try:
            self.hold.wait(timeout=10)
        finally:
            with self._lock:
                self.active["n"] -= 1


class TestE2ESoftTimeoutNoOverlap:
    """Soft-timeout must stay advisory so SKIP_IF_RUNNING prevents worker pile-up."""

    def test_soft_timeout_does_not_start_overlapping_workers(self) -> None:
        probe = _OverlapProbe()
        clock = _Clock()
        orch = self._armed_orchestrator(probe.blocking_ship, clock)
        self._run_past_soft_timeout(orch, clock, probe)
        self._assert_no_overlap_while_held(orch, probe)
        self._assert_can_run_again_after_reap(orch, clock, probe)

    def _armed_orchestrator(self, run: Callable[[], None], clock: _Clock) -> JobOrchestrator:
        orch = JobOrchestrator()
        orch.register(
            JobSpec(
                job_id=JobIds.SERVICE_LOGS,
                schedule=IntervalSchedule(INTERVAL),
                timeout_seconds=SOFT_TIMEOUT,
                queue_policy=QueuePolicy.SKIP_IF_RUNNING,
                run=run,
            )
        )
        orch._arm_first_fires(clock())
        return orch

    def _run_past_soft_timeout(
        self, orch: JobOrchestrator, clock: _Clock, probe: _OverlapProbe
    ) -> None:
        self._dispatch(orch, clock)
        time.sleep(SOFT_TIMEOUT + 0.05)
        for _ in range(OVERLAP_CYCLES):
            clock.advance(INTERVAL)
            self._dispatch(orch, clock)
            time.sleep(0.01)

    def _assert_no_overlap_while_held(
        self, orch: JobOrchestrator, probe: _OverlapProbe
    ) -> None:
        assert max(probe.peaks) == 1, f"overlapping workers: peaks={probe.peaks}"
        assert orch._is_running(JobIds.SERVICE_LOGS)
        assert orch._soft_warned == {JobIds.SERVICE_LOGS}

    def _assert_can_run_again_after_reap(
        self, orch: JobOrchestrator, clock: _Clock, probe: _OverlapProbe
    ) -> None:
        probe.hold.set()
        orch.join_running(timeout=2.0)
        orch._reap_finished()
        assert not orch._is_running(JobIds.SERVICE_LOGS)
        probe.hold.clear()
        clock.advance(INTERVAL)
        self._dispatch(orch, clock)
        time.sleep(0.02)
        assert probe.active["n"] == 1
        assert max(probe.peaks) == 1
        probe.hold.set()
        orch.join_running(timeout=2.0)

    def _dispatch(self, orch: JobOrchestrator, clock: _Clock) -> None:
        def sleep(_delay: float) -> None:
            raise StopIteration

        with pytest.raises(StopIteration):
            orch._cycle(clock, sleep)
