"""Orchestrator sync/render/start/stop."""

from unittest.mock import MagicMock, patch

import pytest

from raft.models.stack import load_stack
from raft.services import Orchestrator

from ...base import write_applied_app
from .base import OrchestratorTestCase


class TestOrchRenderStart(OrchestratorTestCase):
    def test_sync_ensures_upstreams_then_syncer(self) -> None:
        with patch.object(self.orch, "render"):
            self.orch.sync(["app"], ref_override="abc", force=True)
        self.orch.nginx.ensure_steady_file.assert_called()
        self.orch.syncer.sync.assert_called_once()

    def test_sync_all_apps(self) -> None:
        with patch.object(self.orch, "render"):
            self.orch.sync()
        assert self.orch.syncer.sync.call_args.args[0] == list(self.orch.stack.apps)

    def test_render_invokes_stack_renderer(self) -> None:
        self.orch.docker.running_services.return_value = []
        with patch("raft.services.deploy.orchestrator.StackRenderer") as renderer_cls:
            instance = renderer_cls.return_value
            self.orch.render()
            renderer_cls.assert_called_once_with(self.orch.stack)
            instance.render.assert_called_once()
            self.orch.docker.reload_gate_nginx.assert_not_called()

    def test_render_reloads_gate_when_stamp_differs_from_disk(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        with patch("raft.services.deploy.orchestrator.GateNginxStamp") as stamp_cls:
            stamp = stamp_cls.return_value
            stamp.fingerprint.return_value = "disk-fp"
            stamp.read.return_value = "stale-fp"
            with patch("raft.services.deploy.orchestrator.StackRenderer"):
                with patch("raft.services.deploy.orchestrator.require_origin_certs"):
                    self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_called_once()
        stamp.write.assert_called_once_with("disk-fp")

    def test_render_reloads_gate_when_stamp_missing(self) -> None:
        """Disk already has config but gate never recorded a reload (stale process)."""
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        with patch("raft.services.deploy.orchestrator.GateNginxStamp") as stamp_cls:
            stamp = stamp_cls.return_value
            stamp.fingerprint.return_value = "on-disk"
            stamp.read.return_value = None
            with patch("raft.services.deploy.orchestrator.StackRenderer"):
                with patch("raft.services.deploy.orchestrator.require_origin_certs"):
                    self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_called_once()

    def test_render_blocks_gate_reload_when_origin_certs_missing(self) -> None:
        write_applied_app(self.tmp_path, "app", public_host="app.test", tls="origin")
        orch = self.orchestrator()
        orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        with patch("raft.services.deploy.orchestrator.GateNginxStamp") as stamp_cls:
            stamp = stamp_cls.return_value
            stamp.fingerprint.return_value = "disk-fp"
            stamp.read.return_value = "stale"
            with patch("raft.services.deploy.orchestrator.StackRenderer"):
                with pytest.raises(RuntimeError, match="Origin certs missing"):
                    orch.render()
        orch.docker.reload_gate_nginx.assert_not_called()

    def test_render_skips_gate_reload_when_stamp_matches_disk(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        with patch("raft.services.deploy.orchestrator.GateNginxStamp") as stamp_cls:
            stamp = stamp_cls.return_value
            stamp.fingerprint.return_value = "same"
            stamp.read.return_value = "same"
            with patch("raft.services.deploy.orchestrator.StackRenderer"):
                self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_not_called()

    def test_render_skips_gate_reload_when_gate_down(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-router"]
        with patch("raft.services.deploy.orchestrator.GateNginxStamp") as stamp_cls:
            stamp = stamp_cls.return_value
            stamp.fingerprint.return_value = "disk-fp"
            stamp.read.return_value = "stale"
            with patch("raft.services.deploy.orchestrator.StackRenderer"):
                self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_not_called()

    def test_start_happy_path(self) -> None:
        self.orch.docker.running_services.side_effect = [
            [],
            ["raft-gate", "raft-router", "raft-controller", "app"],
        ]
        self.orch.http.public_host_ok.return_value = True
        with patch.object(self.orch, "sync") as sync:
            self.orch.start()
        sync.assert_called_once()
        self.orch.docker.start_stack.assert_called_once()

    def test_start_fails_if_gate_exits(self) -> None:
        self.orch.docker.running_services.side_effect = [
            [],
            ["raft-router", "app"],
        ]
        with patch.object(self.orch, "sync"):
            with pytest.raises(
                RuntimeError,
                match="missing running services: \\['raft-gate', 'raft-controller'\\]",
            ):
                self.orch.start()
        self.orch.docker.start_stack.assert_called_once()

    def test_recreate_gate_happy(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        self.orch.http.tcp_port_ok.return_value = True
        with patch.object(self.orch, "render"):
            self.orch.recreate_gate()
        self.orch.docker.recreate_gate.assert_called_once()

    def test_stop_already_stopped(self) -> None:
        self.orch.docker.running_services.return_value = []
        self.orch.stop()
        self.orch.docker.remove_container.assert_called()
        self.orch.docker.stop_stack.assert_not_called()

    def test_stop_running(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-gate"]
        self.orch.stop()
        self.orch.docker.stop_stack.assert_called_once()

    def test_redeploy_routes_to_router_and_app(self) -> None:
        with patch.object(self.orch, "redeploy_router") as rr:
            self.orch.redeploy("router")
        rr.assert_called_once()
        with patch.object(self.orch, "redeploy_app") as ra:
            self.orch.redeploy("app")
        ra.assert_called_once_with("app")

    def test_redeploy_router_happy(self) -> None:
        self.orch.docker.running_services.return_value = ["raft-gate", "raft-router", "raft-controller"]
        self.orch.http.public_host_ok.return_value = True
        self.orch.redeploy_router()
        self.orch.docker.recreate_router.assert_called_once()

