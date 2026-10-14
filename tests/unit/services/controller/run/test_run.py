"""Controller process wiring (orchestrator + scale side_ticks)."""

import logging
import runpy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.core.core.config.settings.types import (
    HealingConfig,
    MetricsConfig,
    RaftConfig,
    ServiceLogsConfig,
    default_config,
)
from raft.services.controller import PrereqSmoke, main
from raft.services.controller.engine.job import JobIds, QueuePolicy
from raft.services.controller.jobs import ControllerJob
from raft.services.controller.jobs.heal import HealJob
from raft.services.controller.jobs.metrics import MetricsJob
from raft.services.controller.jobs.scale import ScaleJob
from raft.core.core.utils import ControllerLogging
from raft.services.controller.run import ControllerLoop, RaftController, main as main_impl
from raft.services.controller.run.smoke import PrereqSmoke as smoke_impl
from raft.core.core.errors.cta import OperatorError

from tests.unit.services.controller.base import ControllerTestCase


class TestControllerPrereq(ControllerTestCase):
    def test_public_exports(self) -> None:
        assert main is main_impl
        assert PrereqSmoke is smoke_impl

    def test_setup_controller_logging_stdout_only(self) -> None:
        ControllerLogging().configure(RaftConfig())
        root = logging.getLogger("raft")
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.StreamHandler)

    def test_run_prereq_smoke_ok(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        sh = MagicMock()
        version = MagicMock(returncode=0, stdout="27.3.1\n", stderr="")
        compose = MagicMock(returncode=0, stdout="Docker Compose version v2.29.7\n")
        sh.docker.return_value = version
        sh.compose.return_value = compose
        with patch("raft.services.controller.run.smoke.Stack.load_apps") as load_apps:
            load_apps.return_value = MagicMock(apps=(), core_services=("raft-gate",))
            PrereqSmoke(home, sh).run()
        sh.docker.assert_called_once_with(
            "version", "--format", "{{.Server.Version}}", capture=True
        )
        sh.compose.assert_called_once_with("version", capture=True, check=False)

    def test_run_prereq_smoke_unknown_docker_version(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        sh = MagicMock()
        sh.docker.return_value = MagicMock(returncode=0, stdout="  \n")
        sh.compose.return_value = MagicMock(returncode=0, stdout="ok")
        PrereqSmoke(home, sh).run()

    def test_run_prereq_smoke_compose_missing(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        sh = MagicMock()
        sh.docker.return_value = MagicMock(returncode=0, stdout="27.0.0\n")
        sh.compose.return_value = MagicMock(returncode=1, stdout="", stderr="missing")
        with pytest.raises(RuntimeError, match="docker compose plugin"):
            PrereqSmoke(home, sh).run()

    def test_main_smokes_then_loops(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("RAFT_DATA_HOME", str(home))
        with patch("raft.services.controller.run.raft_controller.PrereqSmoke") as smoke_cls:
            with patch("raft.services.controller.run.raft_controller.WakeHttpServer.bind"):
                with patch.object(
                    ControllerLoop, "run", side_effect=StopIteration
                ):
                    with pytest.raises(StopIteration):
                        main()
        smoke_cls.assert_called_once()
        smoke_cls.return_value.run.assert_called_once()

    def test_loop_registers_jobs(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        orch = MagicMock()
        orch.registered_ids.return_value = frozenset()
        orch.run_forever.side_effect = StopIteration
        cfg = RaftConfig(
            healing=HealingConfig(enabled=True, interval_seconds=15.0, timeout_seconds=120.0),
            metrics=MetricsConfig(interval_seconds=60.0, timeout_seconds=30.0),
        )
        with pytest.raises(StopIteration):
            ControllerLoop(home, cfg, MagicMock(), MagicMock()).run(orchestrator=orch)
        self._assert_core_jobs(orch)

    @staticmethod
    def _assert_core_jobs(orch: MagicMock) -> None:
        assert orch.register.call_count == 3
        assert orch.append_side_tick.call_count == 2
        specs = [c.args[0] for c in orch.register.call_args_list]
        by_id = {s.job_id: s for s in specs}
        assert by_id[JobIds.HEAL].timeout_seconds == 120.0
        assert by_id[JobIds.HEAL].queue_policy == QueuePolicy.SKIP_IF_RUNNING
        assert by_id[JobIds.METRICS].timeout_seconds == 30.0
        assert by_id[JobIds.SERVICE_LOGS].timeout_seconds == 30.0
        assert by_id[JobIds.HEAL].schedule.interval_seconds == 15.0
        assert by_id[JobIds.METRICS].schedule.interval_seconds == 60.0
        assert by_id[JobIds.SERVICE_LOGS].schedule.interval_seconds == 5.0

    def test_loop_builds_default_orchestrator(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        scaler = MagicMock()
        cfg = RaftConfig()
        with patch("raft.services.controller.run.controller_loop.JobOrchestrator") as orch_cls:
            orch = MagicMock()
            orch.registered_ids.return_value = frozenset()
            orch_cls.return_value = orch
            orch.run_forever.side_effect = StopIteration
            with pytest.raises(StopIteration):
                ControllerLoop(home, cfg, MagicMock(), scaler).run()
        assert orch_cls.call_count == 1
        assert orch.append_side_tick.call_count == 2
        assert orch.register.call_count == 3

    def test_loop_passes_sleep_and_clock(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        orch = MagicMock()
        orch.registered_ids.return_value = frozenset()
        orch.run_forever.side_effect = StopIteration
        sleep = MagicMock()
        clock = MagicMock()
        with pytest.raises(StopIteration):
            ControllerLoop(home, RaftConfig(), MagicMock(), MagicMock()).run(
                sleep_fn=sleep,
                clock=clock,
                orchestrator=orch,
            )
        orch.run_forever.assert_called_once_with(sleep_fn=sleep, clock=clock)

    def test_nudge_enqueues_metrics(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        orch = MagicMock()
        job = HealJob(home, RaftConfig().healing, MagicMock())
        job.attach(orch)
        assert job._healer.on_needs_heal is not None
        job._healer.on_needs_heal()
        orch.enqueue.assert_called_once()
        assert orch.enqueue.call_args.args[0].job_id == JobIds.METRICS
        job._healer = MagicMock()
        job.tick()
        job._healer.tick.assert_called_once()

    def test_metrics_tick_runs_resource_and_http(self, tmp_path: Path) -> None:
        job = MetricsJob(self.raft_home(tmp_path), RaftConfig().metrics)
        resources = MagicMock()
        http_metrics = MagicMock()
        job._resources = resources
        job._http = http_metrics
        job.tick()
        resources.tick.assert_called_once()
        http_metrics.tick.assert_called_once()

    def test_side_tick_swallows(self, tmp_path: Path) -> None:
        scaler = MagicMock()
        scaler.tick.side_effect = RuntimeError("x")
        ScaleJob(scaler)._as_side_tick()()

    def test_jobs_are_controller_jobs(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        orch = MagicMock()
        jobs = ControllerLoop(
            home, RaftConfig(), MagicMock(), MagicMock()
        )._jobs(orch)
        assert len(jobs) == 5
        assert all(isinstance(j, ControllerJob) for j in jobs)

    def test_log_startup_disabled(self, tmp_path: Path) -> None:
        cfg = RaftConfig(
            healing=HealingConfig(enabled=False),
            metrics=MetricsConfig(),
            service_logs=ServiceLogsConfig(enabled=False),
        )
        ControllerLoop(
            self.raft_home(tmp_path), cfg, MagicMock(), MagicMock()
        )._log_startup()

    def test_log_startup_enabled(self, tmp_path: Path) -> None:
        cfg = RaftConfig(
            healing=HealingConfig(enabled=True),
            metrics=MetricsConfig(),
            service_logs=ServiceLogsConfig(enabled=True),
        )
        ControllerLoop(
            self.raft_home(tmp_path), cfg, MagicMock(), MagicMock()
        )._log_startup()

    def test_main_requires_data_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        missing = tmp_path / "nope"
        monkeypatch.setenv("RAFT_DATA_HOME", str(missing))
        with pytest.raises(OperatorError, match="data home missing"):
            main()

    def test_module_entrypoint(self) -> None:
        with patch("raft.services.controller.run.main", side_effect=SystemExit(0)):
            with pytest.raises(SystemExit):
                runpy.run_module("raft.services.controller", run_name="__main__")

    def test_main_module_import_does_not_run(self) -> None:
        import raft.services.controller.__main__ as controller_main

        assert controller_main.main is main

    def test_raft_controller_run_delegates(self) -> None:
        assert callable(RaftController().run)
