"""Controller process wiring (orchestrator + scale side_ticks)."""

from __future__ import annotations

import logging
import runpy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from raft.config.settings_types import HealingConfig, MetricsConfig, RaftConfig, default_config
from raft.controller import main, run_prereq_smoke
from raft.controller.job import JobId, QueuePolicy
from raft.controller.logging import setup_controller_logging
from raft.controller.run import main as main_impl
from raft.controller.smoke import run_prereq_smoke as smoke_impl
from raft.errors.cta import OperatorError

from .base import ControllerTestCase


class TestControllerPrereq(ControllerTestCase):
    def test_public_exports(self) -> None:
        assert main is main_impl
        assert run_prereq_smoke is smoke_impl

    def test_setup_controller_logging_stdout_only(self) -> None:
        setup_controller_logging(default_config())
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
        with patch("raft.controller.smoke.Stack.load_apps") as load_apps:
            load_apps.return_value = MagicMock(apps=(), core_services=("raft-gate",))
            run_prereq_smoke(home, sh)
        sh.docker.assert_called_once_with(
            "version", "--format", "{{.Server.Version}}", capture=True
        )
        sh.compose.assert_called_once_with("version", capture=True, check=False)

    def test_run_prereq_smoke_unknown_docker_version(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        sh = MagicMock()
        sh.docker.return_value = MagicMock(returncode=0, stdout="  \n")
        sh.compose.return_value = MagicMock(returncode=0, stdout="ok")
        run_prereq_smoke(home, sh)

    def test_run_prereq_smoke_compose_missing(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        sh = MagicMock()
        sh.docker.return_value = MagicMock(returncode=0, stdout="27.0.0\n")
        sh.compose.return_value = MagicMock(returncode=1, stdout="", stderr="missing")
        with pytest.raises(RuntimeError, match="docker compose plugin"):
            run_prereq_smoke(home, sh)

    def test_main_smokes_then_loops(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("RAFT_DATA_HOME", str(home))
        with patch("raft.controller.run.run_prereq_smoke") as smoke:
            with patch("raft.controller.run.start_wake_http"):
                with patch("raft.controller.run._run_forever", side_effect=StopIteration):
                    with pytest.raises(StopIteration):
                        main()
        smoke.assert_called_once()

    def test_run_forever_registers_jobs(self, tmp_path: Path) -> None:
        from raft.controller.run import _run_forever

        home = self.raft_home(tmp_path)
        scaler = MagicMock()
        orch = MagicMock()
        orch.run_forever.side_effect = StopIteration
        cfg = RaftConfig(
            healing=HealingConfig(enabled=True, interval_seconds=15.0, timeout_seconds=120.0),
            metrics=MetricsConfig(interval_seconds=60.0, timeout_seconds=30.0),
        )
        with pytest.raises(StopIteration):
            _run_forever(home, cfg, MagicMock(), scaler, orchestrator=orch)
        assert orch.register.call_count == 2
        specs = [c.args[0] for c in orch.register.call_args_list]
        by_id = {s.job_id: s for s in specs}
        assert by_id[JobId.HEAL].timeout_seconds == 120.0
        assert by_id[JobId.HEAL].queue_policy == QueuePolicy.SKIP_IF_RUNNING
        assert by_id[JobId.METRICS].timeout_seconds == 30.0
        assert by_id[JobId.HEAL].schedule.interval_seconds == 15.0
        assert by_id[JobId.METRICS].schedule.interval_seconds == 60.0

    def test_run_forever_builds_default_orchestrator(self, tmp_path: Path) -> None:
        from raft.controller.run import _run_forever

        home = self.raft_home(tmp_path)
        scaler = MagicMock()
        cfg = default_config()
        with patch("raft.controller.run.JobOrchestrator") as orch_cls:
            orch = MagicMock()
            orch_cls.return_value = orch
            orch.run_forever.side_effect = StopIteration
            with pytest.raises(StopIteration):
                _run_forever(home, cfg, MagicMock(), scaler)
        assert orch_cls.call_count == 1
        assert "side_ticks" in orch_cls.call_args.kwargs
        assert orch.register.call_count == 2

    def test_run_forever_passes_sleep_and_clock(self, tmp_path: Path) -> None:
        from raft.controller.run import _run_forever

        home = self.raft_home(tmp_path)
        orch = MagicMock()
        orch.run_forever.side_effect = StopIteration
        sleep = MagicMock()
        clock = MagicMock()
        with pytest.raises(StopIteration):
            _run_forever(
                home,
                default_config(),
                MagicMock(),
                MagicMock(),
                sleep_fn=sleep,
                clock=clock,
                orchestrator=orch,
            )
        orch.run_forever.assert_called_once_with(sleep_fn=sleep, clock=clock)

    def test_nudge_enqueues_metrics(self, tmp_path: Path) -> None:
        from raft.controller.run import _build_jobs

        home = self.raft_home(tmp_path)
        orch = MagicMock()
        healer, _metrics = _build_jobs(home, default_config(), MagicMock(), orch)
        healer.on_needs_heal()
        orch.enqueue.assert_called_once()
        assert orch.enqueue.call_args.args[0].job_id == JobId.METRICS

    def test_safe_tick_swallows(self) -> None:
        from raft.controller.run import _safe_tick

        def boom() -> None:
            raise RuntimeError("x")

        _safe_tick(boom, "scale")()

    def test_log_startup_disabled(self) -> None:
        from raft.controller.run import _log_startup

        _log_startup(HealingConfig(enabled=False), MetricsConfig())

    def test_log_startup_enabled(self) -> None:
        from raft.controller.run import _log_startup

        _log_startup(HealingConfig(enabled=True), MetricsConfig())

    def test_main_requires_data_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        missing = tmp_path / "nope"
        monkeypatch.setenv("RAFT_DATA_HOME", str(missing))
        with pytest.raises(OperatorError, match="data home missing"):
            main()

    def test_module_entrypoint(self) -> None:
        with patch("raft.controller.run.main", side_effect=SystemExit(0)):
            with pytest.raises(SystemExit):
                runpy.run_module("raft.controller", run_name="__main__")

    def test_main_module_import_does_not_run(self) -> None:
        import raft.controller.__main__ as controller_main

        assert controller_main.main is main
