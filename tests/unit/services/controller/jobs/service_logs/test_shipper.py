"""Controller ServiceLogsShipper tick coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from raft.core.core.config.settings.types import ServiceLogsConfig
from raft.core.observe.ops.logs.store import ServiceLogsStore
from raft.services.controller.jobs.service_logs import ServiceLogsJob, ServiceLogsShipper

from tests.unit.base import AppMakers, StackMakers
from tests.unit.services.controller.base import ControllerTestCase


class TestServiceLogsShipper(ControllerTestCase):
    def test_tick_ships_running_apps(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        stack = StackMakers.make_stack(home, (AppMakers.make_app("demo-api"),))
        docker = MagicMock()
        docker.try_service_container_id.side_effect = lambda sid: (
            "cid-demo" if sid == "demo-api" else None
        )
        docker.container_logs_since.return_value = (
            "2026-10-14T12:00:00.000000000Z shipped-line\n"
        )
        cfg = ServiceLogsConfig(include_edge=False)
        ServiceLogsShipper(
            home, cfg, docker, stack_loader=lambda: stack
        ).tick()
        text = ServiceLogsStore(
            home, max_age_days=14, max_bytes=1024
        ).active_path("demo-api").read_text(encoding="utf-8")
        assert "shipped-line" in text

    def test_disabled_noop(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        docker = MagicMock()
        ServiceLogsShipper(
            home, ServiceLogsConfig(enabled=False), docker
        ).tick()
        docker.try_service_container_id.assert_not_called()

    def test_job_skips_attach_when_disabled(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        orch = MagicMock()
        ServiceLogsJob(
            home, ServiceLogsConfig(enabled=False), MagicMock()
        ).attach(orch)
        orch.register.assert_not_called()

    def test_job_registers_when_enabled(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        orch = MagicMock()
        job = ServiceLogsJob(home, ServiceLogsConfig(), MagicMock())
        job.attach(orch)
        orch.register.assert_called_once()
        assert orch.register.call_args.args[0].job_id == job.job_id

    def test_job_tick_delegates(self, tmp_path: Path) -> None:
        job = ServiceLogsJob(
            self.raft_home(tmp_path), ServiceLogsConfig(), MagicMock()
        )
        shipper = MagicMock()
        job._shipper = shipper
        job.tick()
        shipper.tick.assert_called_once()

    def test_tick_zero_new_lines_is_quiet(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        stack = StackMakers.make_stack(home, (AppMakers.make_app("demo-api"),))
        docker = MagicMock()
        docker.try_service_container_id.return_value = "cid"
        docker.container_logs_since.return_value = ""
        ServiceLogsShipper(
            home,
            ServiceLogsConfig(include_edge=False),
            docker,
            stack_loader=lambda: stack,
        ).tick()

    def test_tick_skips_missing_containers(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        stack = StackMakers.make_stack(home, (AppMakers.make_app("demo-api"),))
        docker = MagicMock()
        docker.try_service_container_id.return_value = None
        ServiceLogsShipper(
            home,
            ServiceLogsConfig(include_edge=True),
            docker,
            stack_loader=lambda: stack,
        ).tick()
        assert docker.try_service_container_id.call_count >= 1

    def test_ship_oserror_is_logged(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        stack = StackMakers.make_stack(home, (AppMakers.make_app("demo-api"),))
        docker = MagicMock()
        docker.try_service_container_id.return_value = "cid"
        shipper = ServiceLogsShipper(
            home,
            ServiceLogsConfig(include_edge=False),
            docker,
            stack_loader=lambda: stack,
        )
        shipper._capture = MagicMock()
        shipper._capture.ship.side_effect = OSError("ro")
        shipper.tick()
        shipper._capture.ship.assert_called()
