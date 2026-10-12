"""Status collect coverage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from raft.core.core.errors.cta import OperatorError
from raft.core.observe.ops.status.allocated import StatusAllocated
from raft.core.observe.ops.status.models import EDGE_CPUS_LIMIT

from tests.unit.base import AppMakers, AppSpecExtras, AppliedInventory, StackMakers
from tests.unit.core.observe.ops.status.base import StatusTestCase
from . import fixtures as status_fx


class TestStatusCollect(StatusTestCase):
    def _idle_status(self, *apps):
        status = self.make_status(apps=apps or (AppMakers.make_app("app"),))
        status_fx.mock_docker_idle(status)
        return status

    def test_collect_running_and_stopped(self) -> None:
        status = self._idle_status(AppMakers.make_app("app"))
        status_fx.wire_gate_router_running(status._containers)
        with self.patch_host():
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
        status = self._idle_status(AppMakers.make_app("web", group="demo"))
        with self.patch_host():
            snap = status.collect()
        gate, router, controller, app = snap.containers
        assert gate.group == router.group == controller.group == "raft"
        assert app.service == "demo-web" and app.app == "web"
        assert app.group == "demo"

    def test_collect_includes_no_port_worker(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "worker",
            source="docker",
            image="ghcr.io/example/worker",
            public_host="",
            build_context=None,
            extra=AppSpecExtras.worker_ports(),
        )
        status = self._idle_status(AppMakers.make_app("worker", public_host=""))
        with self.patch_host():
            snap = status.collect()
        names = [c.service for c in snap.containers]
        assert "worker" in names

    def test_app_allocated_fallback(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("missing"),))
        allocated = StatusAllocated.app(stack, stack.apps[0])
        assert allocated.memory_limit == "128M"
        bad = MagicMock()
        bad.spec_for.side_effect = OperatorError("boom")
        assert StatusAllocated.app(bad, AppMakers.make_app("x")).cpus_limit == "0.50"

    def test_collect_refresh_apps_reloads_registry(self) -> None:
        status = self._idle_status(AppMakers.make_app("app"))
        AppliedInventory.write_applied_app(self.tmp_path, "newbie")
        with self.patch_host():
            snap = status.collect(refresh_apps=True)
        names = [c.service for c in snap.containers]
        assert "app" in names and "newbie" in names
        assert len(status.stack.apps) == 2

    def test_collect_refresh_apps_skips_ensure_raft_home(self) -> None:
        status = self._idle_status(AppMakers.make_app("app"))
        reloaded = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("app"),))
        with self.patch_host():
            with patch(
                "raft.core.observe.ops.status.service.Stack.load_apps",
                return_value=reloaded,
            ) as load_apps:
                with patch("raft.core.core.models.stack.load_stack") as load_stack_fn:
                    with patch("raft.core.core.models.stack.RaftHomeBootstrap") as ensure:
                        status.collect(refresh_apps=True)
        load_apps.assert_called_once_with(self.tmp_path)
        load_stack_fn.assert_not_called()
        ensure.assert_not_called()
        assert status.stack is reloaded
