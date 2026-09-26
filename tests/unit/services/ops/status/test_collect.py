"""Status collect coverage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.errors import OperatorError
from raft.services.ops.status import Status
from raft.services.ops.status.allocated import StatusAllocated
from raft.services.ops.status.models import EDGE_CPUS_LIMIT

from ....base import RaftTestCase, make_app, make_stack, write_applied_app
from .fixtures import StatusFixtures

_HOST_PATCH = "raft.services.ops.status.service.HostProbe.collect"


class TestStatusCollect(RaftTestCase):
    def _idle_status(self, *apps):
        stack = make_stack(self.tmp_path, apps or (make_app("app"),))
        status = Status(stack)
        StatusFixtures.mock_docker_idle(status)
        return status

    def _patch_host(self):
        return patch(_HOST_PATCH, return_value=StatusFixtures.host())

    def test_collect_running_and_stopped(self) -> None:
        write_applied_app(self.tmp_path, "app")
        status = self._idle_status(make_app("app"))
        StatusFixtures.wire_gate_router_running(status.docker)
        with self._patch_host():
            snap = status.collect()
        self._assert_running_gate_router(snap)
        self._assert_stopped_controller_app(snap)

    def _assert_running_gate_router(self, snap) -> None:
        assert snap.host.cpus == 4
        assert snap.host.memory_total_bytes == 8 * 1024**3
        assert len(snap.containers) == 4
        gate, router, *_ = snap.containers
        assert gate.service == "raft-gate"
        assert gate.role == "gate" and gate.group == "raft"
        assert gate.status == "running" and gate.cpu_percent == 0.5
        assert gate.allocated.cpus_limit == EDGE_CPUS_LIMIT
        assert gate.uptime_seconds is not None and gate.uptime_seconds >= 86000
        assert router.service == "raft-router" and router.group == "raft"

    def _assert_stopped_controller_app(self, snap) -> None:
        _, _, controller, app = snap.containers
        assert controller.service == "raft-controller"
        assert controller.role == "controller" and controller.group == "raft"
        assert controller.status == "not running"
        assert controller.allocated.memory_limit == "128M"
        assert app.service == "app" and app.status == "not running"
        assert app.app == "app" and app.group is None
        assert app.cpu_percent is None
        assert app.allocated.cpus_limit == "0.50"

    def test_collect_app_group(self) -> None:
        write_applied_app(self.tmp_path, "web")
        status = self._idle_status(make_app("web", group="demo"))
        with self._patch_host():
            snap = status.collect()
        gate, router, controller, app = snap.containers
        assert gate.group == router.group == controller.group == "raft"
        assert app.service == "demo-web" and app.app == "web"
        assert app.group == "demo"

    def test_app_allocated_fallback(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("missing"),))
        allocated = StatusAllocated.app(stack, stack.apps[0])
        assert allocated.memory_limit == "128M"
        bad = MagicMock()
        bad.spec_for.side_effect = OperatorError("boom")
        assert StatusAllocated.app(bad, make_app("x")).cpus_limit == "0.50"

    def test_collect_refresh_apps_reloads_registry(self) -> None:
        write_applied_app(self.tmp_path, "app")
        status = self._idle_status(make_app("app"))
        write_applied_app(self.tmp_path, "newbie")
        with self._patch_host():
            snap = status.collect(refresh_apps=True)
        names = [c.service for c in snap.containers]
        assert "app" in names and "newbie" in names
        assert len(status.stack.apps) == 2

    def test_collect_refresh_apps_skips_ensure_raft_home(self) -> None:
        write_applied_app(self.tmp_path, "app")
        status = self._idle_status(make_app("app"))
        reloaded = make_stack(self.tmp_path, (make_app("app"),))
        with self._patch_host():
            with patch(
                "raft.services.ops.status.service.Stack.load_apps",
                return_value=reloaded,
            ) as load_apps:
                with patch("raft.models.stack.load_stack") as load_stack_fn:
                    with patch("raft.models.stack.ensure_raft_home") as ensure:
                        status.collect(refresh_apps=True)
        load_apps.assert_called_once_with(self.tmp_path)
        load_stack_fn.assert_not_called()
        ensure.assert_not_called()
        assert status.stack is reloaded
