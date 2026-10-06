"""Dynamic string job ids: parallel dispatch, drop, skip/fail isolation."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import List
from unittest.mock import MagicMock

import pytest

from raft.controller.job import JobIds, JobRequest, JobSpec, JobType, QueuePolicy
from raft.controller.orchestrator import JobOrchestrator
from raft.controller.schedule import IntervalSchedule


class _Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


class _SkipIfRunningPair:
    """Job A holds while running; job B signals each completion."""

    def __init__(self) -> None:
        self.a_runs = 0
        self.b_runs = 0
        self._hold_a = threading.Event()
        self._started_a = threading.Event()
        self._finished_b = threading.Event()

    def run_a(self) -> None:
        self.a_runs += 1
        self._started_a.set()
        self._hold_a.wait(timeout=5)

    def run_b(self) -> None:
        self.b_runs += 1
        self._finished_b.set()

    def await_a_started(self) -> None:
        assert self._started_a.wait(timeout=2), "job a did not start"

    def await_b_finished(self) -> None:
        assert self._finished_b.wait(timeout=2), "job b did not finish"
        self._finished_b.clear()

    def release_a(self) -> None:
        self._hold_a.set()


class TestJobIds:
    def test_singleton_and_subject_keys(self) -> None:
        assert JobIds.of(JobType.HEAL) == JobIds.HEAL == "heal"
        assert JobIds.of(JobType.METRICS) == JobIds.METRICS == "metrics"
        assert JobIds.of(JobType.ACME, "shop") == "acme:shop"
        assert JobIds.of(JobType.ACME, "") == "acme"


class TestDynamicJobIds:
    def _spec(self, job_id: str, run, interval: float = 10.0, timeout: float = 5.0) -> JobSpec:
        return JobSpec(
            job_id=job_id,
            schedule=IntervalSchedule(interval),
            timeout_seconds=timeout,
            queue_policy=QueuePolicy.SKIP_IF_RUNNING,
            run=run,
        )

    def test_register_and_drop_dynamic_ids(self) -> None:
        runs: List[str] = []
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.HEAL, lambda: runs.append("heal")))
        orch._arm_first_fires(clock())
        acme = JobIds.of(JobType.ACME, "a")
        orch.register(self._spec(acme, lambda: runs.append("a")))
        self._run_one_cycle(orch, clock)
        assert "heal" in runs and "a" in runs
        orch.drop(acme)
        assert acme not in orch._specs
        assert acme not in orch._next_due
        with pytest.raises(ValueError, match="unknown"):
            orch.enqueue(JobRequest(acme))

    def test_parallel_overlapping_dynamic_jobs(self) -> None:
        barrier = threading.Barrier(2)
        release, synced = threading.Event(), threading.Event()
        run_a, run_b = self._overlap_pair(barrier, release, synced)
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.of(JobType.ACME, "a"), run_a, timeout=5.0))
        orch.register(self._spec(JobIds.of(JobType.ACME, "b"), run_b, timeout=5.0))
        self._run_cycles(orch, clock, cycles=1)
        assert synced.wait(timeout=2), "acme jobs did not overlap"
        release.set()

    def test_skip_if_running_is_per_id(self) -> None:
        """While A is still running, a due tick skips A but still runs B."""
        pair = _SkipIfRunningPair()
        a_id = JobIds.of(JobType.ACME, "a")
        b_id = JobIds.of(JobType.ACME, "b")
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        orch.register(self._spec(a_id, pair.run_a, interval=1.0))
        orch.register(self._spec(b_id, pair.run_b, interval=1.0))
        self._run_cycles(orch, clock, cycles=1)
        pair.await_a_started()
        pair.await_b_finished()
        assert (pair.a_runs, pair.b_runs) == (1, 1)
        assert orch._is_running(a_id) and not orch._is_running(b_id)
        clock.advance(1.0)
        self._run_one_cycle(orch, clock)
        pair.await_b_finished()
        assert (pair.a_runs, pair.b_runs) == (1, 2)
        pair.release_a()
        orch.join_running(timeout=2.0)

    def _overlap_pair(self, barrier, release, synced):
        def party() -> None:
            try:
                barrier.wait(timeout=2)
                synced.set()
            except threading.BrokenBarrierError:
                pass
            release.wait(timeout=5)

        return party, party

    def test_failure_does_not_skip_sibling(self) -> None:
        runs: List[str] = []

        def boom() -> None:
            raise RuntimeError("acme:a failed")

        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.of(JobType.ACME, "a"), boom))
        orch.register(self._spec(JobIds.of(JobType.ACME, "b"), lambda: runs.append("b")))
        orch.register(self._spec(JobIds.METRICS, lambda: runs.append("m")))
        self._run_cycles(orch, clock, cycles=1)
        orch.join_running(timeout=2.0)
        assert set(runs) == {"b", "m"}

    def test_soft_timeout_does_not_block_sibling_start(self) -> None:
        hold = threading.Event()
        started_slow = threading.Event()
        started_fast = threading.Event()

        def slow() -> None:
            started_slow.set()
            hold.wait(timeout=5)

        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.of(JobType.ACME, "a"), slow, timeout=0.05))
        orch.register(self._spec(JobIds.of(JobType.ACME, "b"), started_fast.set, timeout=0.05))
        t0 = time.monotonic()
        self._run_cycles(orch, clock, cycles=1)
        assert started_fast.wait(timeout=2)
        assert started_slow.wait(timeout=2)
        assert time.monotonic() - t0 < 0.2
        hold.set()

    def test_heal_and_metrics_still_register(self) -> None:
        runs: List[str] = []
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.HEAL, lambda: runs.append("heal")))
        orch.register(self._spec(JobIds.METRICS, lambda: runs.append("metrics")))
        self._run_cycles(orch, clock, cycles=1)
        orch.join_running(timeout=2.0)
        assert set(runs) == {"heal", "metrics"}

    def test_drop_clears_pending(self) -> None:
        orch = JobOrchestrator()
        acme = JobIds.of(JobType.ACME, "a")
        orch.register(self._spec(acme, lambda: None, interval=60.0))
        orch._arm_first_fires(datetime(2026, 1, 1))
        orch._next_due[acme] = datetime(2026, 1, 1) + timedelta(seconds=60)
        orch.enqueue(JobRequest(acme))
        orch.drop(acme)
        assert acme not in orch._pending
        sleep = MagicMock()
        orch._sleep_until_next(_Clock(datetime(2026, 1, 1)), sleep)
        sleep.assert_not_called()

    def test_dispatch_ignores_unknown_id(self) -> None:
        JobOrchestrator()._dispatch(JobIds.of(JobType.ACME, "missing"), advance_schedule=True)

    def test_join_running_waits_for_worker(self) -> None:
        release = threading.Event()
        orch = JobOrchestrator()
        acme = JobIds.of(JobType.ACME, "a")
        orch.register(self._spec(acme, release.wait, interval=10.0, timeout=5.0))
        orch._arm_first_fires(datetime(2026, 1, 1))
        orch._dispatch_cycle(lambda: datetime(2026, 1, 1))
        assert orch._is_running(acme)
        release.set()
        orch.join_running(timeout=2.0)
        assert not orch._is_running(acme)

    def test_soft_timeout_paths(self) -> None:
        hold = threading.Event()
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        acme = JobIds.of(JobType.ACME, "a")
        orch.register(self._spec(acme, hold.wait, interval=1.0, timeout=0.01))
        orch._arm_first_fires(clock())
        orch._dispatch_cycle(clock)
        orch._check_soft_timeouts()  # still under timeout
        time.sleep(0.03)
        orch._check_soft_timeouts()  # warn
        orch._check_soft_timeouts()  # already warned
        self._orphan_worker_soft_check(orch, hold)
        hold.set()

    def _orphan_worker_soft_check(self, orch: JobOrchestrator, hold: threading.Event) -> None:
        # Dead worker → ``not worker.is_alive()`` continue branch.
        dead = threading.Thread(target=lambda: None, daemon=True)
        dead.start()
        dead.join(timeout=1.0)
        orch._workers["dead"] = dead
        orch._check_soft_timeouts()
        orch._workers.pop("dead", None)
        orphan = threading.Thread(target=hold.wait, daemon=True)
        orch._workers["orphan"] = orphan
        orphan.start()
        # Hit each side of ``started is None or timeout is None``.
        orch._timeouts["orphan"] = 1.0
        orch._check_soft_timeouts()
        del orch._timeouts["orphan"]
        orch._started_mono["orphan"] = time.monotonic()
        orch._check_soft_timeouts()
        del orch._started_mono["orphan"]
        orch._check_soft_timeouts()

    def _run_cycles(self, orch: JobOrchestrator, clock: _Clock, *, cycles: int) -> None:
        orch._arm_first_fires(clock())
        for _ in range(cycles):
            self._run_one_cycle(orch, clock)

    def _run_one_cycle(self, orch: JobOrchestrator, clock: _Clock) -> None:
        def sleep(_delay: float) -> None:
            raise StopIteration

        with pytest.raises(StopIteration):
            orch._cycle(clock, sleep)
