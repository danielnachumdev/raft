"""``raft-controller`` process entry (prereq smoke, then job orchestrator)."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from raft.adapters.docker import DockerStack
from raft.adapters.shell import Shell
from raft.config.paths import raft_home
from raft.config.settings import load_config
from raft.config.settings_types import HealingConfig, MetricsConfig, RaftConfig
from raft.errors.cta import OperatorError
from raft.models.stack import Stack

from .acme_jobs import AcmeJobSync
from .heal import Healer
from .job import JobIds, JobRequest, JobSpec, QueuePolicy
from .logging import setup_controller_logging
from .http_metrics import HttpMetricsRecorder
from .metrics import MetricsRecorder
from .orchestrator import ClockFn, JobOrchestrator, SleepFn
from .scale import WAKE_HTTP_PORT, Scaler
from .schedule import IntervalSchedule
from .smoke import PrereqSmoke
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
    PrereqSmoke(home, sh).run()
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
    orch = orchestrator or JobOrchestrator()
    healer, metrics, http_metrics, acme_sync = _build_jobs(home, config, docker, orch)
    orch.append_side_tick(_safe_tick(scaler.tick, "scale"))
    orch.append_side_tick(_safe_tick(acme_sync.tick, "acme-sync"))
    _register_jobs(
        orch, config.healing, config.metrics, healer, metrics, http_metrics
    )
    acme_sync.tick()
    _log_startup(config.healing, config.metrics)
    kwargs = {}
    if sleep_fn is not None:
        kwargs["sleep_fn"] = sleep_fn
    if clock is not None:
        kwargs["clock"] = clock
    orch.run_forever(**kwargs)


def _build_jobs(home, config: RaftConfig, docker: DockerStack, orch: JobOrchestrator):
    def nudge() -> None:
        orch.enqueue(JobRequest(job_id=JobIds.METRICS))

    healer = Healer(home=home, config=config.healing, docker=docker, on_needs_heal=nudge)
    metrics = _resource_recorder(home, config.metrics)
    http_metrics = _http_recorder(home, config.metrics)
    acme_sync = AcmeJobSync(home, docker, orch)
    return healer, metrics, http_metrics, acme_sync


def _resource_recorder(home, metrics_cfg: MetricsConfig) -> MetricsRecorder:
    return MetricsRecorder(
        home,
        batch_size=metrics_cfg.batch_size,
        flush_seconds=metrics_cfg.flush_seconds,
        retention_max_age_days=metrics_cfg.retention_max_age_days,
        retention_max_bytes=metrics_cfg.retention_max_bytes,
    )


def _http_recorder(home, metrics_cfg: MetricsConfig) -> HttpMetricsRecorder:
    return HttpMetricsRecorder(
        home,
        interval_seconds=metrics_cfg.interval_seconds,
        batch_size=metrics_cfg.batch_size,
        flush_seconds=metrics_cfg.flush_seconds,
        retention_max_age_days=metrics_cfg.retention_max_age_days,
        retention_max_bytes=metrics_cfg.retention_max_bytes,
    )


def _register_jobs(
    orch: JobOrchestrator,
    healing: HealingConfig,
    metrics_cfg: MetricsConfig,
    healer: Healer,
    metrics: MetricsRecorder,
    http_metrics: HttpMetricsRecorder,
) -> None:
    orch.register(
        JobSpec(
            job_id=JobIds.HEAL,
            schedule=IntervalSchedule(healing.interval_seconds),
            timeout_seconds=healing.timeout_seconds,
            queue_policy=QueuePolicy.SKIP_IF_RUNNING,
            run=healer.tick,
        )
    )
    orch.register(
        JobSpec(
            job_id=JobIds.METRICS,
            schedule=IntervalSchedule(metrics_cfg.interval_seconds),
            timeout_seconds=metrics_cfg.timeout_seconds,
            queue_policy=QueuePolicy.SKIP_IF_RUNNING,
            run=_metrics_tick(metrics, http_metrics),
        )
    )


def _metrics_tick(
    metrics: MetricsRecorder, http_metrics: HttpMetricsRecorder
) -> Callable[[], None]:
    def run() -> None:
        metrics.tick()
        http_metrics.tick()

    return run


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
        "metrics enabled interval=%ss timeout=%ss "
        "path=state/metrics/resources.jsonl+http.jsonl",
        metrics_cfg.interval_seconds,
        metrics_cfg.timeout_seconds,
    )
