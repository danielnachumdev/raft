"""Unit tests for ServiceActions up / down / redeploy wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from datetime import datetime, timezone

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.state.graph_event_kinds import (
    KIND_SERVICE_UP,
    KIND_SERVICE_DOWN,
)
from raft.core.core.models.state.graph_event_store import GraphEventStore
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.observe.ops.actions import ServiceActions

from tests.unit.base import RaftTestCase, AppMakers, AppliedInventory, StackMakers

_EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)

_SCALING = {
    "idleSeconds": 60,
    "wakeTimeoutSeconds": 30,
    "minUpSeconds": 15,
}


class TestServiceActions(RaftTestCase):
    def _actions(self, *, apps=None) -> tuple[ServiceActions, MagicMock, MagicMock]:
        stack = StackMakers.make_stack(self.tmp_path, apps or (AppMakers.make_app("site"),))
        docker = MagicMock()
        orch = MagicMock()
        return ServiceActions(stack, orchestrator=orch, docker=docker), docker, orch

    def _with_app_locks(self):
        return patch("raft.core.observe.ops.actions.service.AppAndStackLocks")

    def _with_stack_lock(self):
        return patch("raft.core.observe.ops.actions.service.StackLock")

    @staticmethod
    def _enter(mock_cm) -> None:
        mock_cm.return_value.__enter__ = MagicMock()
        mock_cm.return_value.__exit__ = MagicMock(return_value=False)

    def test_start_calls_docker_under_locks(self) -> None:
        actions, docker, _orch = self._actions()
        with self._with_app_locks() as locks:
            self._enter(locks)
            result = actions.up("site")
        docker.start_service.assert_called_once_with("site")
        assert result == {
            "ok": True,
            "action": "up",
            "service": "site",
            "no_deps": False,
            "started_deps": [],
        }
        events = GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
        assert len(events) == 1
        assert events[0].kind == KIND_SERVICE_UP
        assert events[0].service == "site"

    def test_stop_calls_docker(self) -> None:
        actions, docker, _orch = self._actions()
        with self._with_app_locks() as locks:
            self._enter(locks)
            result = actions.down("site")
        docker.stop_service.assert_called_once_with("site")
        assert result["action"] == "down"
        events = GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
        assert len(events) == 1
        assert events[0].kind == KIND_SERVICE_DOWN
        assert events[0].service == "site"
        assert events[0].metadata["app"] == "site"

    def test_start_edge_uses_stack_lock(self) -> None:
        actions, docker, _orch = self._actions()
        with self._with_stack_lock() as locks:
            self._enter(locks)
            actions.up("gate")
        docker.start_service.assert_called_once_with("raft-gate")

    def test_stop_edge_uses_stack_lock(self) -> None:
        actions, docker, _orch = self._actions()
        with self._with_stack_lock() as locks:
            self._enter(locks)
            actions.down("router")
        docker.stop_service.assert_called_once_with("raft-router")
        events = GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
        assert len(events) == 1
        assert events[0].kind == KIND_SERVICE_DOWN
        assert events[0].service == "raft-router"
        assert events[0].metadata == {}

    def test_start_clears_scaled_to_zero(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "site", extra={"scaling": _SCALING})
        ScalingStore(self.tmp_path).mark_scaled_to_zero("site")
        actions, docker, _orch = self._actions(apps=(AppMakers.make_app("site"),))
        with self._with_app_locks() as locks:
            self._enter(locks)
            actions.up("site")
        docker.start_service.assert_called_once_with("site")
        assert not ScalingStore(self.tmp_path).is_scaled_to_zero("site")

    def test_start_clears_scaled_without_scaling_spec(self) -> None:
        """Store flag can linger; clear with default min_up when no scaling block."""
        AppliedInventory.write_applied_app(self.tmp_path, "site")
        ScalingStore(self.tmp_path).mark_scaled_to_zero("site")
        actions, _docker, _orch = self._actions(apps=(AppMakers.make_app("site"),))
        with self._with_app_locks() as locks:
            self._enter(locks)
            actions.up("site")
        assert not ScalingStore(self.tmp_path).is_scaled_to_zero("site")

    def test_stop_marks_scaled_to_zero_when_scaling(self) -> None:
        AppliedInventory.write_applied_app(self.tmp_path, "site", extra={"scaling": _SCALING})
        actions, docker, _orch = self._actions(apps=(AppMakers.make_app("site"),))
        with self._with_app_locks() as locks:
            self._enter(locks)
            actions.down("site")
        docker.stop_service.assert_called_once_with("site")
        assert ScalingStore(self.tmp_path).is_scaled_to_zero("site")

    def test_redeploy_app_delegates(self) -> None:
        actions, _docker, orch = self._actions()
        result = actions.redeploy("site")
        orch.redeploy_app.assert_called_once_with("site")
        assert result["action"] == "redeploy"

    def test_redeploy_router(self) -> None:
        actions, _docker, orch = self._actions()
        result = actions.redeploy("router")
        orch.redeploy_router.assert_called_once()
        assert result["service"] == "raft-router"

    def test_redeploy_gate_calls_redeploy(self) -> None:
        actions, _docker, orch = self._actions()
        result = actions.redeploy("gate")
        orch.redeploy_gate.assert_called_once()
        orch.redeploy.assert_not_called()
        assert result["action"] == "redeploy"
        assert result["service"] == "raft-gate"

    def test_redeploy_controller(self) -> None:
        actions, _docker, orch = self._actions()
        result = actions.redeploy("controller")
        orch.redeploy_controller.assert_called_once()
        assert result["action"] == "redeploy"
        assert result["service"] == "raft-controller"

    def test_redeploy_dashboard_when_enabled(self) -> None:
        self._write_dashboard_enabled(True)
        actions, _docker, orch = self._actions()
        with patch(
            "raft.core.observe.ops.actions.service.HostOneshotGate"
        ) as gate_cls:
            gate_cls.return_value.in_dashboard.return_value = False
            result = actions.redeploy("dashboard")
        orch.redeploy_dashboard.assert_called_once()
        assert result["service"] == "raft-dashboard"
        assert result.get("started") is not True

    def test_redeploy_dashboard_oneshot_when_in_dashboard(self) -> None:
        self._write_dashboard_enabled(True)
        actions, _docker, orch = self._actions()
        result, gate, flight = self._redeploy_dashboard_oneshot(actions)
        orch.redeploy_dashboard.assert_not_called()
        gate.ensure.assert_called_once()
        flight.start.assert_called_once_with(
            ["raft", "redeploy", "dashboard"],
            with_docker=True,
        )
        assert result == {
            "ok": True,
            "action": "redeploy",
            "service": "raft-dashboard",
            "started": True,
            "job_id": "job-abc",
            "coalesced": False,
        }

    def _redeploy_dashboard_oneshot(self, actions: ServiceActions):
        with patch(
            "raft.core.observe.ops.actions.service.HostOneshotGate"
        ) as gate_cls:
            gate = gate_cls.return_value
            gate.in_dashboard.return_value = True
            with patch(
                "raft.core.observe.ops.actions.service.HostOneshotFlight"
            ) as flight_cls:
                flight = flight_cls.return_value
                started = MagicMock(job_id="job-abc", coalesced=False)
                flight.start.return_value = started
                with patch("raft.core.observe.ops.actions.service.Shell"):
                    return actions.redeploy("dashboard"), gate, flight

    def test_redeploy_dashboard_refused_when_disabled(self) -> None:
        self._write_dashboard_enabled(False)
        actions, _docker, orch = self._actions()
        with pytest.raises(OperatorError, match="dashboard.enabled"):
            actions.redeploy("dashboard")
        orch.redeploy_dashboard.assert_not_called()

    def _write_dashboard_enabled(self, enabled: bool) -> None:
        path = self.tmp_path / "host" / "settings.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        flag = "true" if enabled else "false"
        path.write_text(f"dashboard:\n  enabled: {flag}\n", encoding="utf-8")

    def test_unknown_service(self) -> None:
        actions, _docker, _orch = self._actions()
        with pytest.raises(OperatorError, match="unknown"):
            actions.up("missing")

    def test_default_docker_and_orchestrator(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = ServiceActions(stack)
        with patch("raft.core.observe.ops.actions.service.DockerStack") as docker_cls:
            with patch("raft.core.observe.ops.actions.service.Shell"):
                with patch("raft.core.observe.ops.actions.service.Orchestrator") as orch_cls:
                    docker_cls.return_value = MagicMock()
                    orch_cls.return_value = MagicMock()
                    with self._with_app_locks() as locks:
                        self._enter(locks)
                        actions.up("site")
                        actions.redeploy("site")
        docker_cls.assert_called()
        orch_cls.assert_called_once_with(stack)

    def test_bind_stack_updates_targets_and_docker(self) -> None:
        actions, docker, orch = self._actions(apps=(AppMakers.make_app("site"),))
        actions._orch = orch
        refreshed = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"), AppMakers.make_app("demo-api")))
        actions.bind_stack(refreshed)
        assert actions.stack is refreshed
        assert actions._targets.stack is refreshed
        assert actions._orch is None
        assert actions._purge is None
        assert docker.stack is refreshed
        assert actions._resolve("demo-api")[0] == "demo-api"

    def test_purge_returns_reclaim_api(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        purge = MagicMock()
        purge.execute.return_value = MagicMock(
            as_api=MagicMock(
                return_value={
                    "ok": True,
                    "action": "purge",
                    "reclaimed_bytes": 1024,
                    "reclaimed_human": "1.0KiB",
                    "images_bytes": 1024,
                    "builder_bytes": 0,
                }
            )
        )
        actions = ServiceActions(stack, purge=purge)
        assert actions.purge()["reclaimed_bytes"] == 1024
        purge.execute.assert_called_once()

    def test_purge_builds_default_service(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("site"),))
        actions = ServiceActions(stack)
        with patch("raft.core.observe.ops.actions.service.Purge") as purge_cls:
            instance = MagicMock()
            instance.execute.return_value = MagicMock(
                as_api=MagicMock(return_value={"ok": True, "action": "purge"})
            )
            purge_cls.return_value = instance
            assert actions.purge()["ok"] is True
        purge_cls.assert_called_once_with(stack)
