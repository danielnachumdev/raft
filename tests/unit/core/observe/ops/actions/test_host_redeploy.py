"""HostServiceRedeploy argv + sync oneshot for dashboard app redeploy."""

from unittest.mock import MagicMock, patch

from raft.core.observe.ops.actions.host_redeploy import HostServiceRedeploy
from raft.core.observe.ops.actions import ServiceActions
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

    def test_run_ensures_and_oneshot(self) -> None:
        stack = StackMakers.make_stack(self.tmp_path, (AppMakers.make_app("docket"),))
        oneshot = MagicMock()
        gate = MagicMock()
        host = HostServiceRedeploy(stack, oneshot=oneshot, gate=gate)
        app = stack.apps[0]
        host.run(app.compose_id, app)
        gate.ensure.assert_called_once()
        oneshot.run.assert_called_once_with(
            ["raft", "redeploy", "docket"],
            timeout=HostServiceRedeploy._TIMEOUT,
            with_docker=True,
        )


class TestServiceActionsHostRedeploy(RaftTestCase):
    def _actions(self) -> tuple[ServiceActions, MagicMock]:
        stack = StackMakers.make_stack(
            self.tmp_path, (AppMakers.make_app("docket"),)
        )
        orch = MagicMock()
        return ServiceActions(stack, orchestrator=orch, docker=MagicMock()), orch

    def test_app_redeploy_uses_host_oneshot_in_dashboard(self) -> None:
        actions, orch = self._actions()
        with self._patched_host(in_dashboard=True) as host:
            result = actions.redeploy("docket")
        host.run.assert_called_once()
        args = host.run.call_args[0]
        assert args[0] == "docket"
        assert args[1].name == "docket"
        orch.redeploy_app.assert_not_called()
        assert result == {"ok": True, "action": "redeploy", "service": "docket"}

    def test_gate_redeploy_uses_host_oneshot_in_dashboard(self) -> None:
        actions, orch = self._actions()
        with self._patched_host(in_dashboard=True) as host:
            result = actions.redeploy("gate")
        host.run.assert_called_once()
        assert host.run.call_args[0][0] == actions.stack.gate
        orch.redeploy_gate.assert_not_called()
        assert result["service"] == "raft-gate"

    def test_app_redeploy_local_when_not_dashboard(self) -> None:
        actions, orch = self._actions()
        with self._patched_host(in_dashboard=False) as host:
            result = actions.redeploy("docket")
        host.run.assert_not_called()
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
