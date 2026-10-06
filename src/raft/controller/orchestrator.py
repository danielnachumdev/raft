"""Schedule-aware job orchestrator (heal + metrics; scale via side_ticks)."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

from .job import JobRequest, JobSpec, QueuePolicy

logger = logging.getLogger(__name__)

ClockFn = Callable[[], datetime]
SleepFn = Callable[[float], None]
SideTick = Callable[[], None]


class JobOrchestrator:
    """Register periodic jobs, enqueue one-shots, soft-timeout dispatch."""

    def __init__(self, side_ticks: Sequence[SideTick] = ()) -> None:
        self._specs: Dict[str, JobSpec] = {}
        self._next_due: Dict[str, datetime] = {}
        self._pending: Dict[str, JobRequest] = {}
        self._workers: Dict[str, threading.Thread] = {}
        self._started_mono: Dict[str, float] = {}
        self._timeouts: Dict[str, float] = {}
        self._soft_warned: Set[str] = set()
        self._last_now: Optional[datetime] = None
        self._side_ticks: List[SideTick] = list(side_ticks)

    def append_side_tick(self, tick: SideTick) -> None:
        """Add a per-cycle hook (scale, ACME job sync, …)."""
        self._side_ticks.append(tick)

    def register(self, spec: JobSpec) -> None:
        self._specs[spec.job_id] = spec
        self._arm_registered(spec.job_id)

    def registered_ids(self) -> frozenset[str]:
        """Job ids currently scheduled (excludes in-flight dropped workers)."""
        return frozenset(self._specs)

    def drop(self, job_id: str) -> None:
        """Stop scheduling ``job_id``; a running worker is left to finish."""
        self._specs.pop(job_id, None)
        self._next_due.pop(job_id, None)
        self._pending.pop(job_id, None)

    def join_running(self, timeout: Optional[float] = None) -> None:
        """Wait for in-flight workers (virtual-clock tests; not used in prod loop)."""
        for worker in list(self._workers.values()):
            worker.join(timeout=timeout)

    def enqueue(self, request: JobRequest) -> None:
        if request.job_id not in self._specs:
            raise ValueError(f"unknown job id: {request.job_id}")
        # REPLACE any existing pending one-shot for the same id (no unbounded stack).
        self._pending[request.job_id] = request

    def run_forever(
        self,
        *,
        sleep_fn: SleepFn = time.sleep,
        clock: Optional[ClockFn] = None,
    ) -> None:
        clock_fn = clock or self._default_clock
        self._arm_first_fires(clock_fn())
        while True:
            self._cycle(clock_fn, sleep_fn)

    def run_until(
        self,
        predicate: Callable[[], bool],
        *,
        sleep_fn: SleepFn,
        clock: Optional[ClockFn] = None,
    ) -> None:
        """Pump until ``predicate``; arm once. Check after dispatch, before sleep."""
        clock_fn = clock or self._default_clock
        if not self._next_due:
            self._arm_first_fires(clock_fn())
        while not predicate():
            self._dispatch_cycle(clock_fn)
            if predicate():
                return
            self._sleep_until_next(clock_fn, sleep_fn)

    def _arm_registered(self, job_id: str) -> None:
        if job_id in self._next_due or not self._next_due:
            return
        # Match the schedule clock already in use (tests inject naive datetimes).
        self._next_due[job_id] = self._last_now or min(self._next_due.values())

    def _arm_first_fires(self, now: datetime) -> None:
        self._last_now = now
        for job_id in self._specs:
            self._next_due[job_id] = now  # first fire ASAP

    def _cycle(self, clock: ClockFn, sleep_fn: SleepFn) -> None:
        self._dispatch_cycle(clock)
        self._sleep_until_next(clock, sleep_fn)

    def _dispatch_cycle(self, clock: ClockFn) -> None:
        now = clock()
        self._last_now = now
        self._reap_finished()
        self._check_soft_timeouts()
        scheduled, pending_only = self._due_job_ids(now)
        for job_id in scheduled:
            self._dispatch(job_id, advance_schedule=True)
        for job_id in pending_only:
            self._dispatch(job_id, advance_schedule=False)
        self._run_side_ticks()

    def _due_job_ids(self, now: datetime) -> Tuple[List[str], List[str]]:
        scheduled: List[str] = []
        for job_id, when in list(self._next_due.items()):
            if when <= now:
                scheduled.append(job_id)
        pending_only = [job_id for job_id in list(self._pending) if job_id not in scheduled]
        return scheduled, pending_only

    def _dispatch(self, job_id: str, *, advance_schedule: bool) -> None:
        spec = self._specs.get(job_id)
        if spec is None:
            return
        self._pending.pop(job_id, None)
        if advance_schedule and job_id in self._next_due:
            self._next_due[job_id] = spec.schedule.next_fire_after(self._next_due[job_id])
        if self._is_running(job_id) and spec.queue_policy == QueuePolicy.SKIP_IF_RUNNING:
            logger.info("job skip (already running) id=%s", job_id)
            return
        self._start_worker(spec)

    def _start_worker(self, spec: JobSpec) -> None:
        """Start the job thread without joining (siblings run in parallel)."""
        worker = threading.Thread(
            target=self._safe_run,
            args=(spec,),
            name=f"raft-job-{spec.job_id}",
            daemon=True,
        )
        self._workers[spec.job_id] = worker
        self._started_mono[spec.job_id] = time.monotonic()
        self._timeouts[spec.job_id] = spec.timeout_seconds
        self._soft_warned.discard(spec.job_id)
        worker.start()

    def _safe_run(self, spec: JobSpec) -> None:
        try:
            spec.run()
        except Exception:  # noqa: BLE001 — keep orchestrator alive
            logger.exception("job failed id=%s", spec.job_id)

    def _is_running(self, job_id: str) -> bool:
        worker = self._workers.get(job_id)
        return worker is not None and worker.is_alive()

    def _reap_finished(self) -> None:
        for job_id, worker in list(self._workers.items()):
            if worker.is_alive():
                continue
            self._workers.pop(job_id, None)
            self._started_mono.pop(job_id, None)
            self._timeouts.pop(job_id, None)
            self._soft_warned.discard(job_id)

    def _check_soft_timeouts(self) -> None:
        now = time.monotonic()
        for job_id, worker in list(self._workers.items()):
            if not worker.is_alive() or job_id in self._soft_warned:
                continue
            started = self._started_mono.get(job_id)
            timeout = self._timeouts.get(job_id)
            if started is None or timeout is None:
                continue
            if now - started < timeout:
                continue
            logger.warning(
                "job soft-timeout id=%s timeout=%ss (worker continues; skip-if-running)",
                job_id,
                timeout,
            )
            self._soft_warned.add(job_id)

    def _run_side_ticks(self) -> None:
        for tick in self._side_ticks:
            try:
                tick()
            except Exception:  # noqa: BLE001 — keep orchestrator alive
                logger.exception("side tick failed")

    def _sleep_until_next(self, clock: ClockFn, sleep_fn: SleepFn) -> None:
        now = clock()
        if self._pending:
            return
        next_at = min(self._next_due.values()) if self._next_due else now
        delay = (next_at - now).total_seconds()
        if delay > 0:
            sleep_fn(delay)

    @staticmethod
    def _default_clock() -> datetime:
        return datetime.now(timezone.utc)
