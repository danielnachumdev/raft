"""Unit tests for ServeActions start / stop / redeploy wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from datetime import datetime, timezone

from raft.errors.cta import OperatorError
from raft.models.state.graph_event_kinds import (
    KIND_START,
    KIND_STOP,
)
from raft.models.state.graph_event_store import GraphEventStore
from raft.models.state.scaling_store import ScalingStore
from raft.services.serve.actions import ServeActions

from ...base import RaftTestCase, make_app, make_stack, write_applied_app

_EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)

_SCALING = {
    "idleSeconds": 60,
    "wakeTimeoutSeconds": 30,
    "minUpSeconds": 15,
}


class TestServeActions(RaftTestCase):
    def _actions(self, *, apps=None) -> tuple[ServeActions, MagicMock, MagicMock]:
        stack = make_stack(self.tmp_path, apps or (make_app("site"),))
        docker = MagicMock()
        orch = MagicMock()
        return ServeActions(stack, orchestrator=orch, docker=docker), docker, orch

    def _with_app_locks(self):
        return patch("raft.services.serve.actions.app_and_stack_locks")

    def _with_stack_lock(self):
        return patch("raft.services.serve.actions.stack_lock")

    @staticmethod
    def _enter(mock_cm) -> None:
        mock_cm.return_value.__enter__ = MagicMock()
        mock_cm.return_value.__exit__ = MagicMock(return_value=False)

    def test_start_calls_docker_under_locks(self) -> None:
        actions, docker, _orch = self._actions()
        with self._with_app_locks() as locks:
            self._enter(locks)
            result = actions.start("site")
        docker.start_service.assert_called_once_with("site")
        assert result == {"ok": True, "action": "start", "service": "site"}
        events = GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
        assert len(events) == 1
        assert events[0].kind == KIND_START
        assert events[0].service == "site"

    def test_stop_calls_docker(self) -> None:
        actions, docker, _orch = self._actions()
        with self._with_app_locks() as locks:
            self._enter(locks)
            result = actions.stop("site")
        docker.stop_service.assert_called_once_with("site")
        assert result["action"] == "stop"
        events = GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
        assert len(events) == 1
        assert events[0].kind == KIND_STOP
        assert events[0].service == "site"
        assert events[0].metadata["app"] == "site"

    def test_start_edge_uses_stack_lock(self) -> None:
        actions, docker, _orch = self._actions()
        with self._with_stack_lock() as locks:
            self._enter(locks)
            actions.start("gate")
        docker.start_service.assert_called_once_with("raft-gate")

    def test_stop_edge_uses_stack_lock(self) -> None:
        actions, docker, _orch = self._actions()
        with self._with_stack_lock() as locks:
            self._enter(locks)
            actions.stop("router")
        docker.stop_service.assert_called_once_with("raft-router")
        events = GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
        assert len(events) == 1
        assert events[0].kind == KIND_STOP
        assert events[0].service == "raft-router"
        assert events[0].metadata == {}

    def test_start_clears_scaled_to_zero(self) -> None:
        write_applied_app(self.tmp_path, "site", extra={"scaling": _SCALING})
        ScalingStore(self.tmp_path).mark_scaled_to_zero("site")
        actions, docker, _orch = self._actions(apps=(make_app("site"),))
        with self._with_app_locks() as locks:
            self._enter(locks)
            actions.start("site")
        docker.start_service.assert_called_once_with("site")
        assert not ScalingStore(self.tmp_path).is_scaled_to_zero("site")

    def test_start_clears_scaled_without_scaling_spec(self) -> None:
        """Store flag can linger; clear with default min_up when no scaling block."""
        write_applied_app(self.tmp_path, "site")
        ScalingStore(self.tmp_path).mark_scaled_to_zero("site")
        actions, _docker, _orch = self._actions(apps=(make_app("site"),))
        with self._with_app_locks() as locks:
            self._enter(locks)
            actions.start("site")
        assert not ScalingStore(self.tmp_path).is_scaled_to_zero("site")

    def test_stop_marks_scaled_to_zero_when_scaling(self) -> None:
        write_applied_app(self.tmp_path, "site", extra={"scaling": _SCALING})
        actions, docker, _orch = self._actions(apps=(make_app("site"),))
        with self._with_app_locks() as locks:
            self._enter(locks)
            actions.stop("site")
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

    def test_redeploy_gate_refused(self) -> None:
        actions, _docker, orch = self._actions()
        orch.redeploy.side_effect = OperatorError(
            "refusing to redeploy `gate`", has_fix=False
        )
        with pytest.raises(OperatorError, match="gate"):
            actions.redeploy("gate")
        orch.redeploy.assert_called_once_with("gate")

    def test_redeploy_controller_refused(self) -> None:
        actions, _docker, _orch = self._actions()
        with pytest.raises(OperatorError, match="controller"):
            actions.redeploy("controller")

    def test_unknown_service(self) -> None:
        actions, _docker, _orch = self._actions()
        with pytest.raises(OperatorError, match="unknown"):
            actions.start("missing")

    def test_default_docker_and_orchestrator(self) -> None:
        stack = make_stack(self.tmp_path, (make_app("site"),))
        actions = ServeActions(stack)
        with patch("raft.services.serve.actions.DockerStack") as docker_cls:
            with patch("raft.services.serve.actions.Shell"):
                with patch("raft.services.serve.actions.Orchestrator") as orch_cls:
                    docker_cls.return_value = MagicMock()
                    orch_cls.return_value = MagicMock()
                    with self._with_app_locks() as locks:
                        self._enter(locks)
                        actions.start("site")
                        actions.redeploy("site")
        docker_cls.assert_called()
        orch_cls.assert_called_once_with(stack)
