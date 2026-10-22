"""Pure helpers and orchestrator policy without Docker."""

from unittest.mock import patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.lifecycle.deploy.cutover import DEPLOY_CUTOVER
from raft.core.lifecycle.deploy.wait import WaitUntil
from tests.shared.compose_ids import RunningServices
from tests.shared.nginx import NginxEmerg

from tests.unit.cta_asserts import CtaAsserts
from tests.unit.domain_case import DomainTestCase


class TestWaitUntil:
    def test_succeeds(self) -> None:
        calls = {"n": 0}

        def pred() -> bool:
            calls["n"] += 1
            return calls["n"] >= 2

        WaitUntil("ready", pred, timeout=2, interval=0.01).run()
        assert calls["n"] == 2

    def test_times_out(self) -> None:
        with pytest.raises(OperatorError) as caught:
            WaitUntil("never", lambda: False, timeout=0.05, interval=0.01).run()
        CtaAsserts.operator(caught.value, has_fix=False, contains=("never",))

    def test_times_out_includes_diagnostics(self) -> None:
        with pytest.raises(OperatorError) as caught:
            WaitUntil(
                "app_tmp reachable from router",
                lambda: False,
                timeout=0.05,
                interval=0.01,
                fix="raft doctor",
                diagnostics=lambda: ("--- raft-app_tmp ---\n" + NginxEmerg.host_not_found("old")),
            ).run()
        CtaAsserts.operator(
            caught.value,
            contains=("app_tmp", "host not found"),
            fix_label="Fix: raft doctor",
        )

    def test_diagnostics_failure_does_not_mask_timeout(self) -> None:
        def boom() -> str:
            raise RuntimeError("diag failed")

        with pytest.raises(OperatorError) as caught:
            WaitUntil(
                "never",
                lambda: False,
                timeout=0.05,
                interval=0.01,
                diagnostics=boom,
            ).run()
        CtaAsserts.operator(caught.value, has_fix=False, contains=("never",))


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


class TestOrchestratorPolicy(DomainTestCase):
    @pytest.fixture(autouse=True)
    def _policy_setup(self, _applied_stack) -> None:
        self.orch = self.orchestrator(mock_deps=False)

    def test_redeploy_gate_calls_redeploy(self) -> None:
        with patch.object(self.orch, "redeploy_gate") as recreate:
            self.orch.redeploy("gate")
        recreate.assert_called_once()

    def test_redeploy_gate_requires_running(self) -> None:
        with patch.object(self.orch.docker, "running_services", return_value=["router"]):
            with pytest.raises(OperatorError, match="gate"):
                self.orch.redeploy_gate()

    def test_start_refuses_if_running(self) -> None:
        with patch.object(
            self.orch.docker,
            "running_services",
            return_value=RunningServices.edge(),
        ):
            with patch.object(
                self.orch.docker,
                "network_holders",
                return_value=["cling-on"],
            ):
                with pytest.raises(OperatorError, match="already running") as caught:
                    self.orch.up()
        assert "Network holders" in str(caught.value)
        assert "cling-on" in str(caught.value)
        assert "compose.yaml ps" in str(caught.value)

    def test_redeploy_router_requires_gate(self) -> None:
        with patch.object(self.orch.docker, "running_services", return_value=["router"]):
            with pytest.raises(OperatorError, match="gate"):
                self.orch.redeploy_router()
