"""``raft-controller`` process entry (prereq smoke, then job orchestrator)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from ..adapters.docker import DockerStack
from ..adapters.shell import Shell
from ..config.paths import raft_home
from ..config.settings import load_config
from ..config.settings_types import RaftConfig
from ..errors.cta import OperatorError
from ..models.stack import Stack
from ..utils import ControllerLogging
from .jobs import (
    AcmeJobSync,
    ControllerJob,
    HealJob,
    MetricsJob,
    ScaleJob,
    Scaler,
    WAKE_HTTP_PORT,
)
from .orchestrator import ClockFn, JobOrchestrator, SleepFn
from .smoke import PrereqSmoke
from .wake_http import WakeHttpServer

__all__ = ["ControllerLoop", "RaftController", "main"]

logger = logging.getLogger(__name__)


class RaftController:
    """``raft-controller`` process entry: smoke, wake HTTP, then control loop."""

    def run(self) -> None:
        home = self._require_data_home()
        config = load_config(home)
        ControllerLogging().configure(config)
        logger.info("raft-controller starting data_home=%s", home)
        sh = Shell(home)
        PrereqSmoke(home, sh).run()
        logger.info("prereq smoke ok; entering control loop")
        self._start_loop(home, config, sh)

    def _require_data_home(self) -> Path:
        # Host CLI owns ``ensure_raft_home`` / template sync. The controller only
        # consumes the mounted data home (package is on PYTHONPATH, not a pip dist).
        home = raft_home()
        if not home.is_dir():
            raise OperatorError(
                f"raft data home missing: {home}\n"
                f"Fix: run `raft render` (or any raft command) on the host first"
            )
        return home

    def _start_loop(self, home: Path, config: RaftConfig, sh: Shell) -> None:
        stack = Stack(root=home, apps=())
        docker = DockerStack(stack, sh)
        scaler = Scaler(home, docker)
        WakeHttpServer.bind(scaler, port=WAKE_HTTP_PORT)
        ControllerLoop(home, config, docker, scaler).run()


class ControllerLoop:
    """Construct ``ControllerJob``s, attach them, and run the orchestrator."""

    def __init__(
        self,
        home: Path,
        config: RaftConfig,
        docker: DockerStack,
        scaler: Scaler,
    ) -> None:
        self._home = home
        self._config = config
        self._docker = docker
        self._scaler = scaler

    def run(
        self,
        *,
        sleep_fn: Optional[SleepFn] = None,
        clock: Optional[ClockFn] = None,
        orchestrator: Optional[JobOrchestrator] = None,
    ) -> None:
        orch = orchestrator or JobOrchestrator()
        for job in self._jobs(orch):
            job.attach(orch)
        self._log_startup()
        self._run_orchestrator(orch, sleep_fn=sleep_fn, clock=clock)

    def _jobs(self, orch: JobOrchestrator) -> List[ControllerJob]:
        return [
            HealJob(self._home, self._config.healing, self._docker),
            MetricsJob(self._home, self._config.metrics),
            ScaleJob(self._scaler),
            AcmeJobSync(self._home, self._docker, orch),
        ]

    def _log_startup(self) -> None:
        healing = self._config.healing
        metrics_cfg = self._config.metrics
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

    def _run_orchestrator(
        self,
        orch: JobOrchestrator,
        *,
        sleep_fn: Optional[SleepFn],
        clock: Optional[ClockFn],
    ) -> None:
        kwargs = {}
        if sleep_fn is not None:
            kwargs["sleep_fn"] = sleep_fn
        if clock is not None:
            kwargs["clock"] = clock
        orch.run_forever(**kwargs)


def main() -> None:
    """Console / ``python -m raft.controller`` entry."""
    RaftController().run()
