"""AppReadyWait / redeploy_router skip scaled-to-zero and manual-stop."""

from unittest.mock import MagicMock, patch

from raft.core.core.models.app import App
from raft.core.core.models.state.manual_stop_store import ManualStopStore
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.core.models.stack import load_stack
from raft.core.lifecycle.deploy.orchestrator import Orchestrator
from raft.core.lifecycle.deploy.orchestrator.ready import AppReadyWait

from tests.unit.base import AppliedInventory
from tests.unit.core.lifecycle.deploy.orchestrator.base import OrchestratorTestCase


class TestReadyIntentionalDown(OrchestratorTestCase):
    def test_wait_app_ready_skips_scaled_to_zero_compose(self) -> None:
        """Idle scale-to-zero must skip compose readiness (not only Host probes)."""
        self._seed_expose_none_tcp()
        orch = self.orchestrator()
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        with patch("raft.core.lifecycle.deploy.orchestrator.ready.WaitUntil") as wait:
            orch._wait_app_ready(orch.stack.app("app"), timeout=5)
        wait.assert_not_called()

    def test_wait_app_ready_skips_manual_stop(self) -> None:
        self._seed_expose_none_tcp()
        orch = self.orchestrator()
        ManualStopStore(self.tmp_path).mark("app")
        with patch("raft.core.lifecycle.deploy.orchestrator.ready.WaitUntil") as wait:
            orch._wait_app_ready(orch.stack.app("app"), timeout=5)
        wait.assert_not_called()

    def test_skip_intentional_down_false_when_awake(self) -> None:
        orch = self.orchestrator()
        app = App(name="internal", public_host="", source="local", path="services/x/checkout")
        assert AppReadyWait(orch)._skip_intentional_down(app) is False

    def test_redeploy_router_skips_wait_for_intentional_down(self) -> None:
        orch = self._orch_with_live_and_parked_app()
        with patch("raft.core.lifecycle.deploy.orchestrator.ready.WaitUntil") as wait:
            with patch("raft.core.lifecycle.deploy.orchestrator.service.OperatorSay"):
                orch.redeploy_router()
        self._assert_router_wait_skipped_parked(wait)

    def _orch_with_live_and_parked_app(self) -> Orchestrator:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "live",
            public_host="live.test",
            extra={"readiness": {"type": "http", "port": "http", "path": "/"}},
        )
        self._seed_expose_none_tcp()
        orch = Orchestrator(load_stack(self.tmp_path))
        orch.docker = MagicMock()
        orch.nginx = MagicMock()
        orch.http = MagicMock()
        orch.syncer = MagicMock()
        self.set_edge_only(orch=orch)
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        ManualStopStore(self.tmp_path).mark("app")
        self.stub_http_ready(orch.http)
        return orch

    @staticmethod
    def _assert_router_wait_skipped_parked(wait) -> None:
        labels = [call.args[0] for call in wait.call_args_list]
        assert any("live.test" in label for label in labels)
        assert not any("compose readiness for app" in label for label in labels)

    def _seed_expose_none_tcp(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "app",
            public_host="",
            source="docker",
            image="redis",
            build_context=None,
            extra={
                "ports": [{"name": "http", "containerPort": 8000, "expose": "none"}],
                "readiness": {"type": "tcp", "port": "http"},
            },
        )
