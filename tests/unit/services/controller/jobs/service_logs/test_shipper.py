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
            home,
            max_age_days=14,
            max_bytes=1024,
            compose_to_app={"demo-api": "demo-api"},
        ).active_path("demo-api").read_text(encoding="utf-8")
        assert "shipped-line" in text

    def test_disabled_noop(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        docker = MagicMock()
        ServiceLogsShipper(
            home, ServiceLogsConfig(enabled=False), docker
        ).tick()
        docker.try_service_container_id.assert_not_called()

    def test_empty_keys_slice(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        shipper = ServiceLogsShipper(
            home, ServiceLogsConfig(include_edge=False), MagicMock()
        )
        assert shipper._slice([]) == []

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

    def test_round_robin_respects_max_services_per_tick(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        apps = (
            AppMakers.make_app("demo-a"),
            AppMakers.make_app("demo-b"),
            AppMakers.make_app("demo-c"),
        )
        stack = StackMakers.make_stack(home, apps)
        docker = MagicMock()
        docker.try_service_container_id.side_effect = lambda sid: f"cid-{sid}"
        docker.container_logs_since.return_value = ""
        memory = MagicMock()
        memory.elevated.return_value = False
        shipper = ServiceLogsShipper(
            home,
            ServiceLogsConfig(
                include_edge=False, max_services_per_tick=2
            ),
            docker,
            stack_loader=lambda: stack,
            memory=memory,
        )
        shipper.tick()
        first = {
            c.args[0]
            for c in docker.try_service_container_id.call_args_list
        }
        assert len(first) == 2
        docker.try_service_container_id.reset_mock()
        shipper.tick()
        second = {
            c.args[0]
            for c in docker.try_service_container_id.call_args_list
        }
        assert len(second) == 2
        assert first != second or first | second == {"demo-a", "demo-b", "demo-c"}

    def test_pressure_ships_one_service(self, tmp_path: Path) -> None:
        home = self.raft_home(tmp_path)
        apps = (
            AppMakers.make_app("demo-a"),
            AppMakers.make_app("demo-b"),
        )
        stack = StackMakers.make_stack(home, apps)
        docker = MagicMock()
        docker.try_service_container_id.side_effect = lambda sid: f"cid-{sid}"
        docker.container_logs_since.return_value = ""
        memory = MagicMock()
        memory.elevated.return_value = True
        ServiceLogsShipper(
            home,
            ServiceLogsConfig(include_edge=False, max_services_per_tick=4),
            docker,
            stack_loader=lambda: stack,
            memory=memory,
        ).tick()
        assert docker.try_service_container_id.call_count == 1

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
