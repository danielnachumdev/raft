"""HostServiceRedeploy join + unified ServiceActions redeploy wiring."""

from unittest.mock import MagicMock, patch

from raft.core.observe.ops.actions import ServiceActions
from raft.core.observe.ops.actions.host_redeploy import HostServiceRedeploy
from raft.core.platform.adapters.docker import HostOneshotFlight, HostOneshotStart

from tests.unit.base import RaftTestCase, AppMakers, StackMakers


class TestHostServiceRedeployJoin(RaftTestCase):
    def test_join_none_when_idle(self) -> None:
        helper = HostServiceRedeploy(
            StackMakers.make_stack(self.tmp_path, ()), shell=MagicMock()
        )
        flight = MagicMock()
        flight.is_worker.return_value = False
        flight.peek_alive.return_value = None
        with patch.object(helper, "_flight_for", return_value=flight):
            assert helper.join("raft-dashboard", None) is None

    def test_join_none_when_join_alive_empty(self) -> None:
        helper = HostServiceRedeploy(
            StackMakers.make_stack(self.tmp_path, ()), shell=MagicMock()
        )
        flight = MagicMock()
        flight.is_worker.return_value = False
        flight.peek_alive.return_value = "cid-gone"
        flight.join_alive.return_value = None
        with patch.object(helper, "_flight_for", return_value=flight):
            with patch(
                "raft.core.observe.ops.actions.host_redeploy.OperatorSay.say"
            ):
                assert helper.join("raft-dashboard", None) is None

    def test_join_waits_for_live_job(self) -> None:
        helper = HostServiceRedeploy(
            StackMakers.make_stack(self.tmp_path, ()), shell=MagicMock()
        )
        flight = MagicMock()
        flight.is_worker.return_value = False
        flight.peek_alive.return_value = "cid-live-xyz"
        flight.join_alive.return_value = HostOneshotStart(
            job_id="cid-live-xyz", coalesced=True
        )
        with patch.object(helper, "_flight_for", return_value=flight):
            with patch(
                "raft.core.observe.ops.actions.host_redeploy.OperatorSay.say"
            ) as say:
                result = helper.join("raft-dashboard", None)
        assert result is not None
        assert result["coalesced"] is True
        say.assert_called_once()
        assert "dashboard redeploy already in progress" in say.call_args.args[0]

    def test_join_skips_when_this_process_is_worker(self) -> None:
        helper = HostServiceRedeploy(
            StackMakers.make_stack(self.tmp_path, ()), shell=MagicMock()
        )
        flight = MagicMock()
        flight.is_worker.return_value = True
        flight.peek_alive.return_value = "cid-self"
        with patch.object(helper, "_flight_for", return_value=flight):
            with patch(
                "raft.core.observe.ops.actions.host_redeploy.OperatorSay.say"
            ) as say:
                assert helper.join("raft-dashboard", None) is None
        flight.peek_alive.assert_not_called()
        flight.join_alive.assert_not_called()
        say.assert_not_called()

    def test_dashboard_flight_kind_matches_constant(self) -> None:
        assert (
            HostServiceRedeploy.flight_kind("dashboard")
            == HostOneshotFlight.KIND_DASHBOARD_REDEPLOY
        )


class TestServiceActionsUnifiedRedeploy(RaftTestCase):
    def _actions(self) -> tuple[ServiceActions, MagicMock]:
        stack = StackMakers.make_stack(
            self.tmp_path, (AppMakers.make_app("site"),)
        )
        orch = MagicMock()
        return ServiceActions(stack, orchestrator=orch, docker=MagicMock()), orch

    def test_dashboard_redeploy_when_enabled(self) -> None:
        self._write_enabled(True)
        actions, orch = self._actions()
        with self._patched(in_dashboard=False, join=None):
            result = actions.redeploy("dashboard")
        orch.redeploy_dashboard.assert_called_once()
        assert result["service"] == "raft-dashboard"

    def test_dashboard_joins_in_flight(self) -> None:
        self._write_enabled(True)
        actions, orch = self._actions()
        joined = self._payload("raft-dashboard", coalesced=True, job_id="cid-live")
        with self._patched(in_dashboard=False, join=joined):
            result = actions.redeploy("dashboard")
        orch.redeploy_dashboard.assert_not_called()
        assert result == joined

    def test_dashboard_oneshot_in_dashboard(self) -> None:
        self._write_enabled(True)
        actions, orch = self._actions()
        payload = self._payload("raft-dashboard", coalesced=False, job_id="job-abc")
        with self._patched(in_dashboard=True, start=payload) as host:
            result = actions.redeploy("dashboard")
        orch.redeploy_dashboard.assert_not_called()
        host.start.assert_called_once()
        assert host.start.call_args[0][0] == "raft-dashboard"
        assert result == payload

    def test_app_joins_in_flight_on_cli(self) -> None:
        actions, orch = self._actions()
        joined = self._payload("site", coalesced=True, job_id="app-cid")
        with self._patched(in_dashboard=False, join=joined) as host:
            result = actions.redeploy("site")
        host.join.assert_called_once()
        orch.redeploy_app.assert_not_called()
        assert result == joined

    def test_worker_rebuilds_instead_of_joining_self(self) -> None:
        self._write_enabled(True)
        actions, orch = self._actions()
        with self._patched(in_dashboard=False, join=None) as host:
            result = actions.redeploy("dashboard")
        host.join.assert_called_once()
        orch.redeploy_dashboard.assert_called_once()
        assert result["service"] == "raft-dashboard"

    def _payload(self, service: str, *, coalesced: bool, job_id: str) -> dict:
        return {
            "ok": True,
            "action": "redeploy",
            "service": service,
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
                    "raft.core.observe.ops.actions.service.HostServiceRedeploy"
                ) as host_cls:
                    gate_cls.return_value.in_dashboard.return_value = in_dashboard
                    host = host_cls.return_value
                    host.join.return_value = join
                    if start is not None:
                        host.start.return_value = start
                    yield host

        return _cm()

    def _write_enabled(self, enabled: bool) -> None:
        path = self.tmp_path / "host" / "settings.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        flag = "true" if enabled else "false"
        path.write_text(f"dashboard:\n  enabled: {flag}\n", encoding="utf-8")
