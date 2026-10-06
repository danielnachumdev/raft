"""JobOrchestrator: schedules, soft timeout, skip-if-running, side_ticks."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import List
from unittest.mock import MagicMock

import pytest

from raft.controller.job import JobIds, JobRequest, JobSpec, QueuePolicy
from raft.controller.orchestrator import JobOrchestrator
from raft.controller.schedule import CronSchedule, IntervalSchedule


class _Clock:
    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


class TestJobOrchestrator:
    def _spec(self, job_id: str, run, interval: float = 10.0, timeout: float = 1.0) -> JobSpec:
        return JobSpec(
            job_id=job_id,
            schedule=IntervalSchedule(interval),
            timeout_seconds=timeout,
            queue_policy=QueuePolicy.SKIP_IF_RUNNING,
            run=run,
        )

    def test_fires_on_interval_and_side_tick(self) -> None:
        runs: List[str] = []
        side = MagicMock()
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator(side_ticks=[side])
        orch.register(self._spec(JobIds.HEAL, lambda: runs.append("heal"), interval=15.0))

        def sleep(delay: float) -> None:
            clock.advance(delay)
            if len(runs) >= 2:
                raise StopIteration

        with pytest.raises(StopIteration):
            orch.run_forever(sleep_fn=sleep, clock=clock)
        assert runs == ["heal", "heal"]
        assert side.call_count >= 2

    def test_skip_if_running_and_soft_timeout(self) -> None:
        started = threading.Event()
        release = threading.Event()
        runs = {"n": 0}

        def blocking() -> None:
            runs["n"] += 1
            started.set()
            release.wait(timeout=5)

        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.HEAL, blocking, interval=1.0, timeout=0.05))
        self._run_cycles(orch, clock, cycles=1)
        assert started.wait(timeout=2)
        assert runs["n"] == 1
        # Second cycle while first still running → skip
        clock.advance(1.0)
        self._run_one_cycle(orch, clock)
        assert runs["n"] == 1
        release.set()

    def test_one_shot_asap_and_replace_pending(self) -> None:
        runs: List[str] = []
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.METRICS, lambda: runs.append("m"), interval=60.0))
        # Arm schedules without sleeping into periodic fire: enqueue only.
        orch._arm_first_fires(clock())
        orch._next_due[JobIds.METRICS] = clock() + timedelta(seconds=60)
        orch.enqueue(JobRequest(JobIds.METRICS))
        orch.enqueue(JobRequest(JobIds.METRICS))  # replace
        self._run_one_cycle(orch, clock)
        assert runs == ["m"]

    def test_exceptions_swallowed(self) -> None:
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()

        def boom() -> None:
            raise RuntimeError("x")

        orch.register(self._spec(JobIds.HEAL, boom, interval=10.0))
        self._run_cycles(orch, clock, cycles=1)

    def test_side_tick_runs_even_when_jobs_skip(self) -> None:
        side = MagicMock()
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator(side_ticks=[side])
        hold = threading.Event()
        started = threading.Event()

        def blocking() -> None:
            started.set()
            hold.wait(timeout=5)

        orch.register(self._spec(JobIds.HEAL, blocking, interval=1.0, timeout=0.05))
        self._run_cycles(orch, clock, cycles=1)
        assert started.wait(timeout=2)
        clock.advance(1.0)
        self._run_one_cycle(orch, clock)
        assert side.call_count >= 2
        hold.set()

    def test_side_tick_exception_swallowed(self) -> None:
        def bad_side() -> None:
            raise RuntimeError("side")

        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator(side_ticks=[bad_side])
        orch.register(self._spec(JobIds.HEAL, lambda: None, interval=10.0))
        self._run_cycles(orch, clock, cycles=1)

    def test_enqueue_unknown_job(self) -> None:
        orch = JobOrchestrator()
        with pytest.raises(ValueError, match="unknown"):
            orch.enqueue(JobRequest(JobIds.METRICS))

    def test_register_with_cron_schedule(self) -> None:
        runs: List[str] = []
        clock = _Clock(datetime(2026, 1, 1, 12, 0, 0))
        orch = JobOrchestrator()
        orch.register(
            JobSpec(
                job_id=JobIds.METRICS,
                schedule=CronSchedule("*/1 * * * *"),
                timeout_seconds=1.0,
                queue_policy=QueuePolicy.SKIP_IF_RUNNING,
                run=lambda: runs.append("c"),
            )
        )
        self._run_cycles(orch, clock, cycles=1)
        assert runs == ["c"]

    def test_sleep_skips_when_pending(self) -> None:
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.METRICS, lambda: None, interval=60.0))
        orch._arm_first_fires(clock())
        orch._next_due[JobIds.METRICS] = clock() + timedelta(seconds=60)
        orch.enqueue(JobRequest(JobIds.METRICS))
        sleep = MagicMock()
        orch._sleep_until_next(clock, sleep)
        sleep.assert_not_called()

    def test_sleep_skips_non_positive_delay(self) -> None:
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.HEAL, lambda: None, interval=10.0))
        orch._next_due[JobIds.HEAL] = clock()  # due now → delay 0
        sleep = MagicMock()
        orch._sleep_until_next(clock, sleep)
        sleep.assert_not_called()

    def test_run_until_preserves_schedule_across_calls(self) -> None:
        runs: List[str] = []
        clock = _Clock(datetime(2026, 1, 1, 0, 0, 0))
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.HEAL, lambda: runs.append("h"), interval=10.0))
        orch.register(self._spec(JobIds.METRICS, lambda: runs.append("m"), interval=60.0))

        def sleep(delay: float) -> None:
            clock.advance(delay)

        orch.run_until(
            lambda: clock.now.minute >= 0 and len(runs) >= 2, sleep_fn=sleep, clock=clock
        )
        # t=0 fired heal+metrics; next heal at +10. Continue without re-arm.
        before = list(runs)
        orch.run_until(lambda: len(runs) > len(before), sleep_fn=sleep, clock=clock)
        assert runs[len(before) :] == ["h"]
        assert "m" not in runs[len(before) :]

    def test_run_until_noop_when_predicate_already_true(self) -> None:
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.HEAL, lambda: None, interval=10.0))
        sleep = MagicMock()
        orch.run_until(lambda: True, sleep_fn=sleep, clock=_Clock(datetime(2026, 1, 1)))
        sleep.assert_not_called()

    def test_default_clock_path(self) -> None:
        orch = JobOrchestrator()
        orch.register(self._spec(JobIds.HEAL, lambda: None, interval=10.0))
        sleep = MagicMock(side_effect=StopIteration)
        with pytest.raises(StopIteration):
            orch.run_forever(sleep_fn=sleep)
        assert isinstance(JobOrchestrator._default_clock(), datetime)

    def _run_cycles(self, orch: JobOrchestrator, clock: _Clock, *, cycles: int) -> None:
        orch._arm_first_fires(clock())
        for _ in range(cycles):
            self._run_one_cycle(orch, clock)

    def _run_one_cycle(self, orch: JobOrchestrator, clock: _Clock) -> None:
        def sleep(_delay: float) -> None:
            raise StopIteration

        with pytest.raises(StopIteration):
            orch._cycle(clock, sleep)
