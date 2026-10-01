"""Schedule-aware job orchestrator (heal + metrics; scale via side_ticks)."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .job import JobId, JobRequest, JobSpec, QueuePolicy

logger = logging.getLogger(__name__)

ClockFn = Callable[[], datetime]
SleepFn = Callable[[float], None]
SideTick = Callable[[], None]


class JobOrchestrator:
    """Register periodic jobs, enqueue one-shots, soft-timeout dispatch."""

    def __init__(self, side_ticks: Sequence[SideTick] = ()) -> None:
        self._specs: Dict[JobId, JobSpec] = {}
        self._next_due: Dict[JobId, datetime] = {}
        self._pending: Dict[JobId, JobRequest] = {}
        self._workers: Dict[JobId, threading.Thread] = {}
        self._side_ticks: List[SideTick] = list(side_ticks)

    def register(self, spec: JobSpec) -> None:
        self._specs[spec.job_id] = spec

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

    def _arm_first_fires(self, now: datetime) -> None:
        for job_id in self._specs:
            self._next_due[job_id] = now  # first fire ASAP

    def _cycle(self, clock: ClockFn, sleep_fn: SleepFn) -> None:
        self._dispatch_cycle(clock)
        self._sleep_until_next(clock, sleep_fn)

    def _dispatch_cycle(self, clock: ClockFn) -> None:
        now = clock()
        self._reap_finished()
        scheduled, pending_only = self._due_job_ids(now)
        for job_id in scheduled:
            self._dispatch(job_id, advance_schedule=True)
        for job_id in pending_only:
            self._dispatch(job_id, advance_schedule=False)
        self._run_side_ticks()

    def _due_job_ids(self, now: datetime) -> Tuple[List[JobId], List[JobId]]:
        scheduled: List[JobId] = []
        for job_id, when in list(self._next_due.items()):
            if when <= now:
                scheduled.append(job_id)
        pending_only = [job_id for job_id in list(self._pending) if job_id not in scheduled]
        return scheduled, pending_only

    def _dispatch(self, job_id: JobId, *, advance_schedule: bool) -> None:
        spec = self._specs[job_id]
        self._pending.pop(job_id, None)
        if advance_schedule and job_id in self._next_due:
            self._next_due[job_id] = spec.schedule.next_fire_after(self._next_due[job_id])
        if self._is_running(job_id) and spec.queue_policy == QueuePolicy.SKIP_IF_RUNNING:
            logger.info("job skip (already running) id=%s", job_id.value)
            return
        self._start_and_join(spec)

    def _start_and_join(self, spec: JobSpec) -> None:
        worker = threading.Thread(
            target=self._safe_run,
            args=(spec,),
            name=f"raft-job-{spec.job_id.value}",
            daemon=True,
        )
        self._workers[spec.job_id] = worker
        worker.start()
        worker.join(timeout=spec.timeout_seconds)
        if worker.is_alive():
            logger.warning(
                "job soft-timeout id=%s timeout=%ss (worker continues; skip-if-running)",
                spec.job_id.value,
                spec.timeout_seconds,
            )

    def _safe_run(self, spec: JobSpec) -> None:
        try:
            spec.run()
        except Exception:  # noqa: BLE001 — keep orchestrator alive
            logger.exception("job failed id=%s", spec.job_id.value)

    def _is_running(self, job_id: JobId) -> bool:
        worker = self._workers.get(job_id)
        return worker is not None and worker.is_alive()

    def _reap_finished(self) -> None:
        for job_id, worker in list(self._workers.items()):
            if not worker.is_alive():
                self._workers.pop(job_id, None)

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
