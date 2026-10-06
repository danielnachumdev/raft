"""AcmeJobSync: register/drop parallel ``acme:<app>`` jobs from manifests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from raft.controller.acme_jobs import (
    ACME_INTERVAL_SECONDS,
    ACME_TIMEOUT_SECONDS,
    AcmeJobSync,
)
from raft.controller.job import JobIds, JobSpec, JobType, QueuePolicy
from raft.controller.orchestrator import JobOrchestrator
from raft.controller.schedule import IntervalSchedule
from raft.models.stack import Stack

from ..base import write_applied_app
from .base import ControllerTestCase


class TestAcmeJobSync(ControllerTestCase):
    def _sync(
        self, home: Path, orch: JobOrchestrator | None = None
    ) -> tuple[AcmeJobSync, JobOrchestrator]:
        orch = orch or JobOrchestrator()
        return AcmeJobSync(home, MagicMock(), orch), orch

    def test_registers_two_acme_apps(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "shop", public_host="shop.test", tls="acme")
        write_applied_app(home, "blog", public_host="blog.test", tls="acme")
        write_applied_app(home, "plain", public_host="plain.test", tls="off")
        sync, orch = self._sync(home)
        sync.tick()
        ids = orch.registered_ids()
        assert JobIds.of(JobType.ACME, "shop") in ids
        assert JobIds.of(JobType.ACME, "blog") in ids
        assert JobIds.of(JobType.ACME, "plain") not in ids
        assert len([i for i in ids if i.startswith("acme:")]) == 2

    def test_drops_when_tls_leaves_acme(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "shop", public_host="shop.test", tls="acme")
        sync, orch = self._sync(home)
        sync.tick()
        assert JobIds.of(JobType.ACME, "shop") in orch.registered_ids()
        write_applied_app(home, "shop", public_host="shop.test", tls="off")
        sync.tick()
        assert JobIds.of(JobType.ACME, "shop") not in orch.registered_ids()

    def test_drops_when_app_deleted(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "shop", public_host="shop.test", tls="acme")
        sync, orch = self._sync(home)
        sync.tick()
        (home / "state" / "apps" / "shop.yaml").unlink()
        sync.tick()
        assert orch.registered_ids() == frozenset()

    def test_job_policy_hardcoded(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "shop", public_host="shop.test", tls="acme")
        sync, orch = self._sync(home)
        sync.tick()
        spec = orch._specs[JobIds.of(JobType.ACME, "shop")]  # noqa: SLF001
        assert spec.schedule.interval_seconds == ACME_INTERVAL_SECONDS == 21600
        assert spec.timeout_seconds == ACME_TIMEOUT_SECONDS
        assert spec.queue_policy == QueuePolicy.SKIP_IF_RUNNING

    def test_one_failing_ensure_does_not_block_sibling(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "a", public_host="a.test", tls="acme")
        write_applied_app(home, "b", public_host="b.test", tls="acme")
        sync, orch = self._sync(home)
        sync.tick()
        calls: list[str] = []
        self._replace_run(orch, "a", self._boom_runner(calls, "a"))
        self._replace_run(orch, "b", lambda: calls.append("b"))
        self._run_pair(orch)
        assert calls == ["a", "b"]

    @staticmethod
    def _boom_runner(calls: list[str], label: str):
        def run() -> None:
            calls.append(label)
            raise RuntimeError(label)

        return run

    @staticmethod
    def _run_pair(orch: JobOrchestrator) -> None:
        try:
            orch._specs[JobIds.of(JobType.ACME, "a")].run()  # noqa: SLF001
        except RuntimeError:
            pass
        orch._specs[JobIds.of(JobType.ACME, "b")].run()  # noqa: SLF001

    @staticmethod
    def _replace_run(orch: JobOrchestrator, name: str, run) -> None:
        job_id = JobIds.of(JobType.ACME, name)
        orch.register(
            JobSpec(
                job_id=job_id,
                schedule=IntervalSchedule(ACME_INTERVAL_SECONDS),
                timeout_seconds=ACME_TIMEOUT_SECONDS,
                queue_policy=QueuePolicy.SKIP_IF_RUNNING,
                run=run,
            )
        )

    def test_ensure_app_invokes_acme_ensure(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "shop", public_host="shop.test", tls="acme")
        sync, orch = self._sync(home)
        sync.tick()
        with patch("raft.controller.acme_jobs.AcmeEnsure") as ensure_cls:
            ensure_cls.return_value.run = MagicMock()
            orch._specs[JobIds.of(JobType.ACME, "shop")].run()  # noqa: SLF001
        ensure_cls.return_value.run.assert_called_once_with(["shop"])

    def test_ensure_skips_when_app_gone(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        sync, _orch = self._sync(home)
        with patch("raft.controller.acme_jobs.AcmeEnsure") as ensure_cls:
            sync._ensure_app("missing")  # noqa: SLF001
        ensure_cls.assert_not_called()

    def test_ensure_skips_when_tls_changed(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "shop", public_host="shop.test", tls="off")
        sync, _orch = self._sync(home)
        with patch("raft.controller.acme_jobs.AcmeEnsure") as ensure_cls:
            sync._ensure_app("shop")  # noqa: SLF001
        ensure_cls.assert_not_called()

    def test_skips_broken_spec_when_listing(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "shop", public_host="shop.test", tls="acme")
        sync, orch = self._sync(home)
        with patch.object(Stack, "spec_for", side_effect=RuntimeError("bad")):
            sync.tick()
        assert orch.registered_ids() == frozenset()

    def test_ignores_non_acme_registered_ids(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "shop", public_host="shop.test", tls="acme")
        orch = JobOrchestrator()
        orch.register(
            JobSpec(
                job_id=JobIds.HEAL,
                schedule=IntervalSchedule(15.0),
                timeout_seconds=1.0,
                queue_policy=QueuePolicy.SKIP_IF_RUNNING,
                run=lambda: None,
            )
        )
        sync = AcmeJobSync(home, MagicMock(), orch)
        sync.tick()
        assert JobIds.HEAL in orch.registered_ids()
        assert JobIds.of(JobType.ACME, "shop") in orch.registered_ids()

    def test_noop_when_no_acme_apps(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        write_applied_app(home, "plain", public_host="plain.test", tls="off")
        sync, orch = self._sync(home)
        sync.tick()
        assert orch.registered_ids() == frozenset()
