"""Idle / not-running deploys skip ``*_tmp`` dual-run cutover."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from raft.core.core.errors.cta import OperatorError
from raft.core.core.models.state.scaling_store import ScalingStore
from raft.core.core.models.stack import load_stack
from tests.unit.services.controller.base import ControllerTestCase

from tests.unit.base import AppliedInventory
from tests.unit.core.lifecycle.deploy.orchestrator.base import OrchestratorTestCase


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
        self.orch.nginx.point_absent.assert_called_once_with(
            self.orch.stack.app("app"), reload=False
        )
        self.orch.nginx.point_steady.assert_called_once_with(
            self.orch.stack.app("app"), reload=False
        )
        assert not ScalingStore(self.tmp_path).is_scaled_to_zero("app")

    def test_redeploy_skips_tmp_when_not_running(self) -> None:
        self.set_edge_only()
        self.stub_http_ready(self.orch.http)
        with patch("raft.core.lifecycle.deploy.methods.strategies.seamless.CutoverSession") as Session:
            with patch.object(self.orch, "sync") as sync:
                self.orch.redeploy_app("app", ref_override="sha", force_sync=True)
        Session.assert_not_called()
        sync.assert_called_once_with(["app"], ref_override="sha", force=True)
        self.orch.docker.rebuild_service.assert_called_once_with("app")
        self.orch.nginx.point_absent.assert_called()
        self.orch.nginx.point_steady.assert_called()

    def test_redeploy_skips_tmp_when_scaled_to_zero(self) -> None:
        self._seed_scaling_app()
        self.set_edge_running("app")
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        self.stub_http_ready(self.orch.http)
        with patch("raft.core.lifecycle.deploy.methods.strategies.seamless.CutoverSession") as Session:
            with patch.object(self.orch, "sync"):
                self.orch.redeploy_app("app")
        Session.assert_not_called()
        self.orch.docker.rebuild_service.assert_called_once_with("app")
        self.orch.nginx.point_absent.assert_called()
        self.orch.nginx.point_steady.assert_called()
        state = ScalingStore(self.tmp_path).load("app")
        assert not state.scaled_to_zero and state.min_up_until is not None

    def test_idle_docker_source_pulls_instead_of_rebuild(self) -> None:
        self._seed_docker_scaling_app()
        self.set_edge_only()
        ScalingStore(self.tmp_path).mark_scaled_to_zero("app")
        self.stub_http_ready(self.orch.http)
        with patch.object(self.orch, "sync"):
            self.orch.ensure_app_deployed("app", ref_override="abc123", force_sync=True)
        self.orch.docker.rebuild_service.assert_not_called()
        self.orch.docker.recreate_pulled_service.assert_called_once()
        pull_ref = self.orch.docker.recreate_pulled_service.call_args.kwargs["pull_ref"]
        assert "abc123" in pull_ref
        self.orch.nginx.point_absent.assert_called()
        self.orch.nginx.point_steady.assert_called()

    def test_wanted_image_tag_from_ref_state(self) -> None:
        self._seed_docker_scaling_app()
        app = self.orch.stack.app("app")
        path = self.orch.stack.ref_state_file(app)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("digest\n# requested: pin-tag\n", encoding="utf-8")
        assert self.orch._wanted_image_tag(app, ref_override=None) == "pin-tag"
        path.write_text("digest\n# requested:   \n", encoding="utf-8")
        assert self.orch._wanted_image_tag(app, ref_override=None) == app.ref
        path.write_text("digest\n", encoding="utf-8")
        assert self.orch._wanted_image_tag(app, ref_override=None) == app.ref
        path.unlink()
        assert self.orch._wanted_image_tag(app, ref_override=None) == app.ref

    def test_min_up_seconds_defaults_on_spec_error(self) -> None:
        from raft.core.core.models.stack import Stack

        app = self.orch.stack.app("app")
        with patch.object(Stack, "spec_for", side_effect=OperatorError("boom")):
            assert self.orch._min_up_seconds(app) == 60.0

    def test_min_up_seconds_reads_scaling_spec(self) -> None:
        self._seed_scaling_app()
        app = self.orch.stack.app("app")
        assert self.orch._min_up_seconds(app) == float(
            self.orch.stack.spec_for(app).scaling.min_up_seconds
        )

    def test_min_up_seconds_defaults_when_scaling_absent(self) -> None:
        from raft.core.core.models.stack import Stack

        app = self.orch.stack.app("app")
        with patch.object(
            Stack, "spec_for", return_value=SimpleNamespace(scaling=None)
        ):
            assert self.orch._min_up_seconds(app) == 60.0

    def test_redeploy_requires_gate_when_idle(self) -> None:
        self.set_running()
        with pytest.raises(RuntimeError, match="is not running"):
            self.orch.redeploy_app("app")

    def _seed_scaling_app(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "app",
            public_host="app.test",
            extra=ControllerTestCase.scaling_extra(),
        )
        self.orch = self.orchestrator()

    def _seed_docker_scaling_app(self) -> None:
        AppliedInventory.write_applied_app(
            self.tmp_path,
            "app",
            public_host="app.test",
            source="docker",
            image="ghcr.io/example/app",
            extra=ControllerTestCase.scaling_extra(),
        )
        self.stack = load_stack(self.tmp_path)
        self.orch = self.orchestrator()
