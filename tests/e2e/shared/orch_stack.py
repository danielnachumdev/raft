"""Real-Docker harness: JobOrchestrator drives heal + metrics on a fake clock."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, List, Optional

import yaml

from raft.adapters.docker import DockerStack
from raft.adapters.shell import Shell
from raft.config.settings_types import HealingConfig
from raft.controller.heal import Healer
from raft.controller.job import JobIds, JobRequest, JobSpec, QueuePolicy
from raft.controller.metrics import MetricsRecorder
from raft.controller.orchestrator import JobOrchestrator
from raft.controller.schedule import IntervalSchedule
from raft.models.stack import load_stack
from tests.e2e.shared.compose import apps_only_compose, new_project_name
from tests.e2e.shared.runtime import ServiceRuntimeWait
from tests.shared.raft_home import RaftHomeFixtures

# CI-fast intervals: heal fires more often than metrics; gap proves one-shot nudge.
HEAL_INTERVAL = 10.0
METRICS_INTERVAL = 60.0
HEAL_TIMEOUT = 60.0
METRICS_TIMEOUT = 30.0


class VirtualClock:
    """Injectable wall clock for orchestrator tests."""

    def __init__(self, start: Optional[datetime] = None) -> None:
        self.now = start or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)

    @property
    def elapsed(self) -> float:
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return (self.now - start).total_seconds()


class OrchE2EStack:
    """Apps-only Compose + JobOrchestrator (heal + metrics; no scale job)."""

    APP = "http-only"
    FIXTURE = "http_only"

    def __init__(
        self,
        home: Path,
        project: str,
        docker: DockerStack,
        healer: Healer,
        metrics: MetricsRecorder,
        orch: JobOrchestrator,
        clock: VirtualClock,
        heal_fires: List[float],
        metrics_fires: List[float],
    ) -> None:
        self.home = home
        self.project = project
        self.docker = docker
        self.healer = healer
        self.metrics = metrics
        self.orch = orch
        self.clock = clock
        self.heal_fires = heal_fires
        self.metrics_fires = metrics_fires

    @classmethod
    def create(cls, home: Path) -> "OrchE2EStack":
        project = new_project_name()
        RaftHomeFixtures.apply_and_render(home, RaftHomeFixtures.fixture_app_yamls(cls.FIXTURE))
        model = load_stack(home)
        cls._install_apps_compose(home, project)
        docker = DockerStack(model, Shell(home))
        clock = VirtualClock()
        heal_fires: List[float] = []
        metrics_fires: List[float] = []
        stack = cls._wire(home, project, docker, clock, heal_fires, metrics_fires)
        stack._compose_up()
        stack.wait_runtime("running")
        return stack

    @classmethod
    def _wire(
        cls,
        home: Path,
        project: str,
        docker: DockerStack,
        clock: VirtualClock,
        heal_fires: List[float],
        metrics_fires: List[float],
    ) -> "OrchE2EStack":
        orch = JobOrchestrator(side_ticks=[])
        healer = Healer(
            home,
            cls._healing(),
            docker,
            on_needs_heal=lambda: orch.enqueue(JobRequest(job_id=JobIds.METRICS)),
        )
        metrics = MetricsRecorder(
            home,
            batch_size=1,
            flush_seconds=1.0,
            collect_fn=lambda: {"host": {}, "containers": []},
        )
        cls._register(orch, healer, metrics, clock, heal_fires, metrics_fires)
        return cls(home, project, docker, healer, metrics, orch, clock, heal_fires, metrics_fires)

    @staticmethod
    def _register(
        orch: JobOrchestrator,
        healer: Healer,
        metrics: MetricsRecorder,
        clock: VirtualClock,
        heal_fires: List[float],
        metrics_fires: List[float],
    ) -> None:
        heal_run, metrics_run = OrchE2EStack._counted_runs(
            healer, metrics, clock, heal_fires, metrics_fires
        )
        orch.register(OrchE2EStack._heal_spec(heal_run))
        orch.register(OrchE2EStack._metrics_spec(metrics_run))

    @staticmethod
    def _counted_runs(healer, metrics, clock, heal_fires, metrics_fires):
        def heal_run() -> None:
            heal_fires.append(clock.elapsed)
            healer.tick()

        def metrics_run() -> None:
            metrics_fires.append(clock.elapsed)
            metrics.tick()

        return heal_run, metrics_run

    @staticmethod
    def _heal_spec(run) -> JobSpec:
        return JobSpec(
            job_id=JobIds.HEAL,
            schedule=IntervalSchedule(HEAL_INTERVAL),
            timeout_seconds=HEAL_TIMEOUT,
            queue_policy=QueuePolicy.SKIP_IF_RUNNING,
            run=run,
        )

    @staticmethod
    def _metrics_spec(run) -> JobSpec:
        return JobSpec(
            job_id=JobIds.METRICS,
            schedule=IntervalSchedule(METRICS_INTERVAL),
            timeout_seconds=METRICS_TIMEOUT,
            queue_policy=QueuePolicy.SKIP_IF_RUNNING,
            run=run,
        )

    def run_until(self, predicate: Callable[[], bool]) -> None:
        """Drive cycles until predicate; preserves schedule across calls.

        Join workers before the predicate / sleep decision so (1) SKIP_IF_RUNNING
        does not burn slots while a Docker tick is still running, and (2) heal's
        one-shot enqueue is visible to ``_sleep_until_next`` before the clock
        jumps to the next periodic due time.
        """

        def sleep(delay: float) -> None:
            if delay > 0:
                self.clock.advance(delay)

        def ready() -> bool:
            self.orch.join_running()
            return predicate()

        self.orch.run_until(ready, sleep_fn=sleep, clock=self.clock)

    def stop_app(self) -> None:
        self.docker.sh.compose("stop", self.APP, check=True, capture=True)
        self.wait_not_running()

    def wait_not_running(self, *, timeout: float = 45.0) -> None:
        ServiceRuntimeWait(self.docker, self.APP).until_stopped(
            timeout=timeout,
            message=f"{self.APP} still running (project={self.project})",
        )

    def wait_runtime(self, status: str, *, timeout: float = 45.0) -> None:
        ServiceRuntimeWait(self.docker, self.APP).until_status(
            status,
            timeout=timeout,
            message=f"{self.APP} wanted status={status!r} (project={self.project})",
        )

    def close(self) -> None:
        self.metrics.flush()
        self.docker.stop_stack()

    def __enter__(self) -> "OrchE2EStack":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _compose_up(self) -> None:
        self.docker.sh.compose("up", "-d", "--pull", "missing", check=True, capture=True)

    @staticmethod
    def _healing() -> HealingConfig:
        return HealingConfig(
            enabled=True,
            interval_seconds=HEAL_INTERVAL,
            timeout_seconds=HEAL_TIMEOUT,
            fail_threshold=1,
            cooldown_seconds=0.0,
            max_restarts=1,
            escalate_after_restarts=1,
        )

    @staticmethod
    def _install_apps_compose(home: Path, project: str) -> None:
        generated = home / "generated"
        scratch = generated / "compose.e2e.yaml"
        apps_only_compose(generated, scratch)
        doc = yaml.safe_load(scratch.read_text(encoding="utf-8")) or {}
        doc["name"] = project
        (home / "compose.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
