"""Idle / not-running deploys skip ``*_tmp`` dual-run cutover."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from raft.errors.cta import OperatorError
from raft.models.state.scaling_store import ScalingStore
from tests.unit.controller.base import ControllerTestCase

from tests.unit.base import write_applied_app
from .base import OrchestratorTestCase


class TestIdleSingleStart(OrchestratorTestCase):
    def test_ensure_skips_cutover_when_scaled_idle(self) -> None:
        self.set_edge_running("app")
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        self.stub_http_ready(self.orch.http)
        with patch.object(self.orch, "redeploy_app") as redeploy:
            with patch.object(self.orch, "sync") as sync:
                self.orch.ensure_app_deployed("app", ref_override="v2", force_sync=True)
        redeploy.assert_not_called()
        sync.assert_called_once_with(["app"], ref_override="v2", force=True)
        self.orch.docker.rebuild_service.assert_called_once_with("app")
        assert not ScalingStore(self.tmp_path).is_scaled_to_zero("app")

    def test_redeploy_skips_tmp_when_not_running(self) -> None:
        self.set_edge_only()
        self.stub_http_ready(self.orch.http)
        with patch("raft.deploy.methods.strategies.seamless.CutoverSession") as Session:
            with patch.object(self.orch, "sync") as sync:
                self.orch.redeploy_app("app", ref_override="sha", force_sync=True)
        Session.assert_not_called()
        sync.assert_called_once_with(["app"], ref_override="sha", force=True)
        self.orch.docker.rebuild_service.assert_called_once_with("app")

    def test_redeploy_skips_tmp_when_scaled_to_zero(self) -> None:
        self._seed_scaling_app()
        self.set_edge_running("app")
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        self.stub_http_ready(self.orch.http)
        with patch("raft.deploy.methods.strategies.seamless.CutoverSession") as Session:
            with patch.object(self.orch, "sync"):
                self.orch.redeploy_app("app")
        Session.assert_not_called()
        self.orch.docker.rebuild_service.assert_called_once_with("app")
        state = ScalingStore(self.tmp_path).load("app")
        assert not state.scaled_to_zero and state.min_up_until is not None

    def test_min_up_seconds_defaults_on_spec_error(self) -> None:
        from raft.models.stack import Stack

        app = self.orch.stack.app("app")
        with patch.object(Stack, "spec_for", side_effect=OperatorError("boom")):
            assert self.orch._min_up_seconds(app) == 60.0

    def test_redeploy_requires_gate_when_idle(self) -> None:
        self.set_running()
        with pytest.raises(RuntimeError, match="is not running"):
            self.orch.redeploy_app("app")

    def _seed_scaling_app(self) -> None:
        write_applied_app(
            self.tmp_path,
            "app",
            public_host="app.test",
            extra=ControllerTestCase.scaling_extra(),
        )
        self.orch = self.orchestrator()
