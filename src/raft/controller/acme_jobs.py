"""Sync per-app ``acme:<name>`` controller jobs from applied ``tls: acme`` Apps."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Set

from raft.adapters.docker import DockerStack
from raft.config.settings import load_config
from raft.models.stack import Stack
from raft.acme.ensure import AcmeEnsure
from raft.acme.install import AcmeGateInstall

from .job import JobIds, JobSpec, JobType, QueuePolicy
from .orchestrator import JobOrchestrator
from .schedule import IntervalSchedule

logger = logging.getLogger(__name__)

# Hardcoded ACME job policy (no settings/env knobs for cadence or queue).
ACME_INTERVAL_SECONDS = 6 * 60 * 60  # ~6h renewal checks
ACME_TIMEOUT_SECONDS = 300.0


class AcmeJobSync:
    """Register / drop ``acme:<app>`` jobs to match applied ``tls: acme`` manifests."""

    def __init__(
        self,
        home: Path,
        docker: DockerStack,
        orch: JobOrchestrator,
    ) -> None:
        self._home = home
        self._docker = docker
        self._orch = orch

    def tick(self) -> None:
        """Align orchestrator ACME jobs with the current applied App set."""
        desired = self._desired_names()
        current = self._registered_subjects()
        for name in sorted(desired - current):
            self._register(name)
        for name in sorted(current - desired):
            self._drop(name)

    def _desired_names(self) -> Set[str]:
        stack = Stack.load_apps(self._home)
        names: Set[str] = set()
        for app in stack.apps:
            try:
                if stack.spec_for(app).tls == "acme":
                    names.add(app.name)
            except Exception:  # noqa: BLE001 — skip broken manifests
                continue
        return names

    def _registered_subjects(self) -> Set[str]:
        prefix = f"{JobType.ACME.value}:"
        out: Set[str] = set()
        for job_id in self._orch.registered_ids():
            if job_id.startswith(prefix):
                out.add(job_id[len(prefix) :])
        return out

    def _register(self, name: str) -> None:
        job_id = JobIds.of(JobType.ACME, name)
        self._orch.register(
            JobSpec(
                job_id=job_id,
                schedule=IntervalSchedule(ACME_INTERVAL_SECONDS),
                timeout_seconds=ACME_TIMEOUT_SECONDS,
                queue_policy=QueuePolicy.SKIP_IF_RUNNING,
                run=self._runner_for(name),
            )
        )
        logger.info("registered ACME job %s", job_id)

    def _drop(self, name: str) -> None:
        job_id = JobIds.of(JobType.ACME, name)
        self._orch.drop(job_id)
        logger.info("dropped ACME job %s", job_id)

    def _runner_for(self, name: str):
        def run() -> None:
            self._ensure_app(name)

        return run

    def _ensure_app(self, name: str) -> None:
        stack = Stack.load_apps(self._home)
        try:
            app = stack.app(name)
        except Exception:  # noqa: BLE001 — deleted mid-flight
            logger.info("ACME job skip: app %r no longer applied", name)
            return
        if stack.spec_for(app).tls != "acme":
            logger.info("ACME job skip: app %r left tls: acme", name)
            return
        config = load_config(self._home).acme
        AcmeEnsure(
            stack,
            installer=AcmeGateInstall(stack, self._docker),
            config=config,
        ).run([name])
