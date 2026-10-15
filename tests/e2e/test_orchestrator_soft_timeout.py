"""E2E: soft-timeout must not stack overlapping job workers (controller OOM root cause)."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import List

import pytest

from raft.services.controller.engine.job import JobIds, JobSpec, QueuePolicy
from raft.services.controller.engine.orchestrator import JobOrchestrator
from raft.services.controller.engine.schedule import IntervalSchedule

pytestmark = pytest.mark.e2e

# Mirror production service-logs shape (scaled for the test): short interval + soft budget.
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


class TestE2ESoftTimeoutNoOverlap:
    """Reproduce the service-logs soft-timeout pile-up and assert it no longer happens.

    Production failure: soft-timeout *forgot* the live worker so SKIP_IF_RUNNING
    allowed another tick while ``docker logs`` children from the first were still
    running → memory climbed to the 128MiB controller cgroup → OOM crash loop and
    metrics gaps. Soft-timeout must stay advisory: one worker until it finishes.
    """

    def test_soft_timeout_does_not_start_overlapping_workers(self) -> None:
        hold = threading.Event()
        active = {"n": 0}
        peaks: List[int] = []
        lock = threading.Lock()

        def blocking_ship() -> None:
            with lock:
                active["n"] += 1
                peaks.append(active["n"])
            try:
                hold.wait(timeout=10)
            finally:
                with lock:
                    active["n"] -= 1

        clock = _Clock()
        orch = JobOrchestrator()
        orch.register(
            JobSpec(
                job_id=JobIds.SERVICE_LOGS,
                schedule=IntervalSchedule(INTERVAL),
                timeout_seconds=SOFT_TIMEOUT,
                queue_policy=QueuePolicy.SKIP_IF_RUNNING,
                run=blocking_ship,
            )
        )
        orch._arm_first_fires(clock())
        self._dispatch(orch, clock)
        time.sleep(SOFT_TIMEOUT + 0.05)
        for _ in range(OVERLAP_CYCLES):
            clock.advance(INTERVAL)
            self._dispatch(orch, clock)
            time.sleep(0.01)

        assert max(peaks) == 1, f"overlapping workers piled up: peaks={peaks}"
        assert orch._is_running(JobIds.SERVICE_LOGS)
        assert orch._soft_warned == {JobIds.SERVICE_LOGS}

        hold.set()
        orch.join_running(timeout=2.0)
        orch._reap_finished()
        assert not orch._is_running(JobIds.SERVICE_LOGS)

        hold.clear()
        clock.advance(INTERVAL)
        self._dispatch(orch, clock)
        time.sleep(0.02)
        assert active["n"] == 1
        assert max(peaks) == 1
        hold.set()
        orch.join_running(timeout=2.0)

    def _dispatch(self, orch: JobOrchestrator, clock: _Clock) -> None:
        def sleep(_delay: float) -> None:
            raise StopIteration

        with pytest.raises(StopIteration):
            orch._cycle(clock, sleep)
