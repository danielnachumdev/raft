"""DashboardRedeploy helpers + ServiceActions dashboard wiring."""

from unittest.mock import MagicMock, patch

from raft.core.observe.ops.actions import ServiceActions
from raft.core.observe.ops.actions.dashboard_redeploy import DashboardRedeploy
from raft.core.platform.adapters.docker import HostOneshotGate

from tests.unit.base import RaftTestCase, AppMakers, StackMakers


class TestDashboardRedeploy(RaftTestCase):
    def test_start_oneshot_payload(self) -> None:
        helper = DashboardRedeploy(
            StackMakers.make_stack(self.tmp_path, ()), shell=MagicMock()
        )
        gate = MagicMock(spec=HostOneshotGate)
        flight = MagicMock()
        flight.start.return_value = MagicMock(job_id="job-1", coalesced=False)
        with patch.object(helper, "flight", return_value=flight):
            result = helper.start_oneshot("raft-dashboard", gate)
        gate.ensure.assert_called_once()
        assert result["job_id"] == "job-1"
        assert result["coalesced"] is False

    def test_join_oneshot_none_when_idle(self) -> None:
        helper = DashboardRedeploy(
            StackMakers.make_stack(self.tmp_path, ()), shell=MagicMock()
        )
        flight = MagicMock()
        flight.peek_alive.return_value = None
        with patch.object(helper, "flight", return_value=flight):
            assert helper.join_oneshot("raft-dashboard") is None

    def test_join_oneshot_waits_for_live_job(self) -> None:
        helper = DashboardRedeploy(
            StackMakers.make_stack(self.tmp_path, ()), shell=MagicMock()
        )
        flight = MagicMock()
        flight.peek_alive.return_value = "cid-live-xyz"
        flight.join_alive.return_value = MagicMock(
            job_id="cid-live-xyz", coalesced=True
        )
        with patch.object(helper, "flight", return_value=flight):
            with patch(
                "raft.core.observe.ops.actions.dashboard_redeploy.OperatorSay.say"
            ):
                result = helper.join_oneshot("raft-dashboard")
        assert result is not None
        assert result["coalesced"] is True


class TestServiceActionsDashboard(RaftTestCase):
    def _actions(self) -> tuple[ServiceActions, MagicMock, MagicMock]:
        stack = StackMakers.make_stack(
            self.tmp_path, (AppMakers.make_app("site"),)
        )
        docker, orch = MagicMock(), MagicMock()
        return ServiceActions(stack, orchestrator=orch, docker=docker), docker, orch

    def test_redeploy_when_enabled(self) -> None:
        self._write_enabled(True)
        actions, _docker, orch = self._actions()
        with self._patched(in_dashboard=False, join=None):
            result = actions.redeploy("dashboard")
        orch.redeploy_dashboard.assert_called_once()
        assert result["service"] == "raft-dashboard"

    def test_redeploy_joins_in_flight(self) -> None:
        self._write_enabled(True)
        actions, _docker, orch = self._actions()
        joined = self._payload(coalesced=True, job_id="cid-live")
        with self._patched(in_dashboard=False, join=joined):
            result = actions.redeploy("dashboard")
        orch.redeploy_dashboard.assert_not_called()
        assert result == joined

    def test_redeploy_oneshot_in_dashboard(self) -> None:
        self._write_enabled(True)
        actions, _docker, orch = self._actions()
        payload = self._payload(coalesced=False, job_id="job-abc")
        with self._patched(in_dashboard=True, start=payload) as (gate, helper):
            result = actions.redeploy("dashboard")
        orch.redeploy_dashboard.assert_not_called()
        helper.start_oneshot.assert_called_once_with("raft-dashboard", gate)
        assert result == payload

    def _payload(self, *, coalesced: bool, job_id: str) -> dict:
        return {
            "ok": True,
            "action": "redeploy",
            "service": "raft-dashboard",
            "started": True,
            "job_id": job_id,
            "coalesced": coalesced,
        }

    def _patched(self, *, in_dashboard: bool, join=None, start=None):
        from contextlib import contextmanager

        @contextmanager
        def _cm():
            with patch(
                "raft.core.observe.ops.actions.service.HostOneshotGate"
            ) as gate_cls:
                with patch(
                    "raft.core.observe.ops.actions.service.DashboardRedeploy"
                ) as help_cls:
                    gate = gate_cls.return_value
                    gate.in_dashboard.return_value = in_dashboard
                    helper = help_cls.return_value
                    helper.join_oneshot.return_value = join
                    if start is not None:
                        helper.start_oneshot.return_value = start
                    yield gate, helper

        return _cm()

    def _write_enabled(self, enabled: bool) -> None:
        path = self.tmp_path / "host" / "settings.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        flag = "true" if enabled else "false"
        path.write_text(f"dashboard:\n  enabled: {flag}\n", encoding="utf-8")
