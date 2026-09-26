"""Stats collect coverage."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from raft.errors import OperatorError
from raft.services.stats import Stats
from raft.services.stats.models import EDGE_CPUS_LIMIT
from raft.services.stats.service import _app_allocated

from ...base import RaftTestCase, make_app, make_stack, write_applied_app
from .fixtures import StatsFixtures


class TestStatsCollect(RaftTestCase):
    def _idle_stats(self, *apps):
        stack = make_stack(self.tmp_path, apps or (make_app("app"),))
        stats = Stats(stack)
        StatsFixtures.mock_docker_idle(stats)
        return stats

    def _patch_host(self):
        return patch(
            "raft.services.stats.service.collect_host_resources",
            return_value=StatsFixtures.host(),
        )

    def test_collect_running_and_stopped(self) -> None:
        write_applied_app(self.tmp_path, "app")
        stats = self._idle_stats(make_app("app"))
        StatsFixtures.wire_gate_router_running(stats.docker)
        with self._patch_host():
            snap = stats.collect()
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
        stats = self._idle_stats(make_app("web", group="demo"))
        with self._patch_host():
            snap = stats.collect()
        gate, router, controller, app = snap.containers
        assert gate.group == router.group == controller.group == "raft"
        assert app.service == "demo-web" and app.app == "web"
        assert app.group == "demo"

    def test_app_allocated_fallback(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("missing"),))
        allocated = _app_allocated(stack, stack.apps[0])
        assert allocated.memory_limit == "128M"
        bad = MagicMock()
        bad.spec_for.side_effect = OperatorError("boom")
        assert _app_allocated(bad, make_app("x")).cpus_limit == "0.50"

    def test_collect_refresh_apps_reloads_registry(self) -> None:
        write_applied_app(self.tmp_path, "app")
        stats = self._idle_stats(make_app("app"))
        write_applied_app(self.tmp_path, "newbie")
        with self._patch_host():
            snap = stats.collect(refresh_apps=True)
        names = [c.service for c in snap.containers]
        assert "app" in names and "newbie" in names
        assert len(stats.stack.apps) == 2
