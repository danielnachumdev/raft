"""Pure helpers and orchestrator policy without Docker."""

from unittest.mock import patch

import pytest

from raft.services import DEPLOY_CUTOVER, wait_until

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
        with pytest.raises(RuntimeError, match="timed out waiting"):
            wait_until("never", lambda: False, timeout=0.05, interval=0.01)


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
        with pytest.raises(RuntimeError, match="raft gate recreate"):
            self.orch.redeploy("gate")

    def test_recreate_gate_requires_running(self) -> None:
        with patch.object(self.orch.docker, "running_services", return_value=["router"]):
            with pytest.raises(RuntimeError, match="gate is not running"):
                self.orch.recreate_gate()

    def test_start_refuses_if_running(self) -> None:
        with patch.object(self.orch.docker, "running_services", return_value=["gate", "router"]):
            with pytest.raises(RuntimeError, match="already running"):
                self.orch.start()

    def test_redeploy_router_requires_gate(self) -> None:
        with patch.object(self.orch.docker, "running_services", return_value=["router"]):
            with pytest.raises(RuntimeError, match="gate is not running"):
                self.orch.redeploy_router()
