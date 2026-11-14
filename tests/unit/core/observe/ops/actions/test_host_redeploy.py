"""HostServiceRedeploy argv + detached oneshot for dashboard app redeploy."""

from unittest.mock import MagicMock, patch

from raft.core.observe.ops.actions.host_redeploy import HostServiceRedeploy
from raft.core.observe.ops.actions import ServiceActions
from raft.core.platform.adapters.docker import HostOneshotStart
from tests.unit.base import RaftTestCase, AppMakers, StackMakers


class TestHostServiceRedeploy(RaftTestCase):
    def test_argv_for_app_and_edge(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("docket"),))
        host = HostServiceRedeploy(stack, shell=MagicMock())
        app = stack.apps[0]
        assert host.argv(app.compose_id, app) == ["raft", "redeploy", "docket"]
        assert host.argv(stack.gate, None) == ["raft", "redeploy", "gate"]
        assert host.argv(stack.router, None) == ["raft", "redeploy", "router"]
        assert host.argv(stack.controller, None) == [
            "raft",
            "redeploy",
            "controller",
        ]
        assert host.flight_kind("docket") == "redeploy-docket"

    def test_start_ensures_and_detaches(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("docket"),))
        gate = MagicMock()
        flight = MagicMock()
        flight.start.return_value = HostOneshotStart(
            job_id="abc123", coalesced=False
        )
        host = HostServiceRedeploy(stack, gate=gate, flight=flight)
        app = stack.apps[0]
        result = host.start(app.compose_id, app)
        gate.ensure.assert_called_once()
        flight.start.assert_called_once_with(
            ["raft", "redeploy", "docket"], with_docker=True
        )
        assert result == {
            "ok": True,
            "action": "redeploy",
            "service": "docket",
            "started": True,
            "job_id": "abc123",
            "coalesced": False,
        }


class TestServiceActionsHostRedeploy(RaftTestCase):
    def _actions(self) -> tuple[ServiceActions, MagicMock]:
        stack = StackMakers.make_stack(
            self.tmp_path, (AppMakers.make_app("docket"),)
        )
        orch = MagicMock()
        return ServiceActions(stack, orchestrator=orch, docker=MagicMock()), orch

    def test_app_redeploy_uses_host_oneshot_in_dashboard(self) -> None:
        actions, orch = self._actions()
        payload = {
            "ok": True,
            "action": "redeploy",
            "service": "docket",
            "started": True,
            "job_id": "jid",
            "coalesced": False,
        }
        with self._patched_host(in_dashboard=True) as host:
            host.start.return_value = payload
            result = actions.redeploy("docket")
        host.start.assert_called_once()
        args = host.start.call_args[0]
        assert args[0] == "docket"
        assert args[1].name == "docket"
        orch.redeploy_app.assert_not_called()
        assert result == payload

    def test_gate_redeploy_uses_host_oneshot_in_dashboard(self) -> None:
        actions, orch = self._actions()
        with self._patched_host(in_dashboard=True) as host:
            host.start.return_value = {
                "ok": True,
                "action": "redeploy",
                "service": actions.stack.gate,
                "started": True,
                "job_id": "g1",
                "coalesced": True,
            }
            result = actions.redeploy("gate")
        host.start.assert_called_once()
        assert host.start.call_args[0][0] == actions.stack.gate
        orch.redeploy_gate.assert_not_called()
        assert result["started"] is True
        assert result["service"] == "raft-gate"

    def test_app_redeploy_local_when_not_dashboard(self) -> None:
        actions, orch = self._actions()
        with self._patched_host(in_dashboard=False) as host:
            result = actions.redeploy("docket")
        host.start.assert_not_called()
        orch.redeploy_app.assert_called_once_with("docket")
        assert result["action"] == "redeploy"

    def _patched_host(self, *, in_dashboard: bool):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            with patch(
                "raft.core.observe.ops.actions.service.HostOneshotGate"
            ) as gate_cls:
                with patch(
                    "raft.core.observe.ops.actions.service.HostServiceRedeploy"
                ) as host_cls:
                    gate_cls.return_value.in_dashboard.return_value = in_dashboard
                    yield host_cls.return_value

        return _cm()
