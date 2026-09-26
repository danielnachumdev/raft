"""Pure helpers and orchestrator policy without Docker."""

from unittest.mock import patch

import pytest

from raft.errors import OperatorError
from raft.services.deploy.cutover import DEPLOY_CUTOVER
from raft.services.deploy.wait import wait_until

from tests.shared.compose_ids import RunningServices
from tests.shared.nginx import NginxEmerg

from ..cta_asserts import assert_operator
from .base import ServicesTestCase


class TestWaitUntil:
    def test_succeeds(self) -> None:
        calls = {"n": 0}

        def pred() -> bool:
            calls["n"] += 1
            return calls["n"] >= 2

        wait_until("ready", pred, timeout=2, interval=0.01)
        assert calls["n"] == 2

    def test_times_out(self) -> None:
        with pytest.raises(OperatorError) as caught:
            wait_until("never", lambda: False, timeout=0.05, interval=0.01)
        assert_operator(caught.value, has_fix=False, contains=("never",))

    def test_times_out_includes_diagnostics(self) -> None:
        with pytest.raises(OperatorError) as caught:
            wait_until(
                "app_tmp reachable from router",
                lambda: False,
                timeout=0.05,
                interval=0.01,
                fix="raft doctor",
                diagnostics=lambda: (
                    "--- raft-app_tmp ---\n" + NginxEmerg.host_not_found("old")
                ),
            )
        assert_operator(
            caught.value,
            contains=("app_tmp", "host not found"),
            fix_label="Fix: raft doctor",
        )

    def test_diagnostics_failure_does_not_mask_timeout(self) -> None:
        def boom() -> str:
            raise RuntimeError("diag failed")

        with pytest.raises(OperatorError) as caught:
            wait_until(
                "never",
                lambda: False,
                timeout=0.05,
                interval=0.01,
                diagnostics=boom,
            )
        assert_operator(caught.value, has_fix=False, contains=("never",))


class TestDeployCutover:
    def test_step_keys(self) -> None:
        keys = [s.key for s in DEPLOY_CUTOVER]
        assert keys == [
            "snapshot_previous_image",
            "start_tmp_from_previous",
            "shift_traffic_to_tmp",
            "rebuild_stable_service",
            "shift_traffic_to_stable",
            "remove_tmp",
        ]


class TestOrchestratorPolicy(ServicesTestCase):
    @pytest.fixture(autouse=True)
    def _policy_setup(self, _services_setup) -> None:
        self.orch = self.orchestrator(mock_deps=False)

    def test_redeploy_refuses_gate(self) -> None:
        with pytest.raises(OperatorError, match="gate recreate"):
            self.orch.redeploy("gate")

    def test_recreate_gate_requires_running(self) -> None:
        with patch.object(self.orch.docker, "running_services", return_value=["router"]):
            with pytest.raises(OperatorError, match="gate"):
                self.orch.recreate_gate()

    def test_start_refuses_if_running(self) -> None:
        with patch.object(
            self.orch.docker,
            "running_services",
            return_value=RunningServices.edge(),
        ):
            with pytest.raises(OperatorError, match="already running"):
                self.orch.start()

    def test_redeploy_router_requires_gate(self) -> None:
        with patch.object(self.orch.docker, "running_services", return_value=["router"]):
            with pytest.raises(OperatorError, match="gate"):
                self.orch.redeploy_router()
