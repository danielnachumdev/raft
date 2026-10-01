"""``raft-controller`` process entry (prereq smoke, then job orchestrator)."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from raft.adapters.docker import DockerStack
from raft.adapters.shell import Shell
from raft.config.paths import raft_home
from raft.config.settings import load_config
from raft.config.settings_types import HealingConfig, MetricsConfig, RaftConfig
from raft.errors import OperatorError
from raft.models.stack import Stack

from .heal import Healer
from .job import JobId, JobRequest, JobSpec, QueuePolicy
from .logging import setup_controller_logging
from .metrics import MetricsRecorder
from .orchestrator import ClockFn, JobOrchestrator, SleepFn
from .scale import WAKE_HTTP_PORT, Scaler
from .schedule import IntervalSchedule
from .smoke import run_prereq_smoke
from .wake_http import start_wake_http

__all__ = ["main"]

logger = logging.getLogger(__name__)

SafeTick = Callable[[], None]


def main() -> None:
    # Host CLI owns ``ensure_raft_home`` / template sync. The controller only
    # consumes the mounted data home (package is on PYTHONPATH, not a pip dist).
    home = raft_home()
    if not home.is_dir():
        raise OperatorError(
            f"raft data home missing: {home}\n"
            f"Fix: run `raft render` (or any raft command) on the host first"
        )
    config = load_config(home)
    setup_controller_logging(config)
    logger.info("raft-controller starting data_home=%s", home)
    sh = Shell(home)
    run_prereq_smoke(home, sh)
    logger.info("prereq smoke ok; entering control loop")
    stack = Stack(root=home, apps=())
    docker = DockerStack(stack, sh)
    scaler = Scaler(home, docker)
    start_wake_http(scaler, port=WAKE_HTTP_PORT)
    _run_forever(home, config, docker, scaler)


def _run_forever(
    home,
    config: RaftConfig,
    docker: DockerStack,
    scaler: Scaler,
    *,
    sleep_fn: Optional[SleepFn] = None,
    clock: Optional[ClockFn] = None,
    orchestrator: Optional[JobOrchestrator] = None,
) -> None:
    orch = orchestrator or JobOrchestrator(
        side_ticks=[_safe_tick(scaler.tick, "scale")],
    )
    healer, metrics = _build_jobs(home, config, docker, orch)
    _register_jobs(orch, config.healing, config.metrics, healer, metrics)
    _log_startup(config.healing, config.metrics)
    kwargs = {}
    if sleep_fn is not None:
        kwargs["sleep_fn"] = sleep_fn
    if clock is not None:
        kwargs["clock"] = clock
    orch.run_forever(**kwargs)


def _build_jobs(home, config: RaftConfig, docker: DockerStack, orch: JobOrchestrator):
    def nudge() -> None:
        orch.enqueue(JobRequest(job_id=JobId.METRICS))

    healer = Healer(home=home, config=config.healing, docker=docker, on_needs_heal=nudge)
    metrics = MetricsRecorder(
        home,
        batch_size=config.metrics.batch_size,
        flush_seconds=config.metrics.flush_seconds,
    )
    return healer, metrics


def _register_jobs(
    orch: JobOrchestrator,
    healing: HealingConfig,
    metrics_cfg: MetricsConfig,
    healer: Healer,
    metrics: MetricsRecorder,
) -> None:
    orch.register(
        JobSpec(
            job_id=JobId.HEAL,
            schedule=IntervalSchedule(healing.interval_seconds),
            timeout_seconds=healing.timeout_seconds,
            queue_policy=QueuePolicy.SKIP_IF_RUNNING,
            run=healer.tick,
        )
    )
    orch.register(
        JobSpec(
            job_id=JobId.METRICS,
            schedule=IntervalSchedule(metrics_cfg.interval_seconds),
            timeout_seconds=metrics_cfg.timeout_seconds,
            queue_policy=QueuePolicy.SKIP_IF_RUNNING,
            run=metrics.tick,
        )
    )


def _safe_tick(fn: Callable[[], None], label: str) -> SafeTick:
    def wrapped() -> None:
        try:
            fn()
        except Exception:  # noqa: BLE001 — keep the controller alive
            logger.exception("%s tick failed", label)

    return wrapped


def _log_startup(healing: HealingConfig, metrics_cfg: MetricsConfig) -> None:
    if healing.enabled:
        logger.info(
            "healing enabled interval=%ss timeout=%ss failThreshold=%s",
            healing.interval_seconds,
            healing.timeout_seconds,
            healing.fail_threshold,
        )
    else:
        logger.info("healing disabled; scale + idle wake loop active")
    logger.info("scale-to-zero enabled for apps with spec.scaling")
    logger.info(
        "metrics enabled interval=%ss timeout=%ss path=state/metrics/resources.jsonl",
        metrics_cfg.interval_seconds,
        metrics_cfg.timeout_seconds,
    )
