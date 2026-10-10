"""Orchestrator sync/render/start/stop."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from raft.adapters import DockerStack
from raft.errors.cta import OperatorError
from raft.models.state.graph_event_kinds import (
    KIND_DEPLOYMENT,
    KIND_DOWN,
    KIND_GATE_RECREATE,
    KIND_UP,
)
from raft.models.state.graph_event_store import GraphEventStore
from tests.shared.compose_ids import RunningServices
from tests.unit.base import completed

from tests.unit.base import write_applied_app
from .base import OrchestratorTestCase

_EPOCH = datetime(2020, 1, 1, tzinfo=timezone.utc)


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
        self.set_running()
        with patch("raft.deploy.orchestrator.StackRenderer") as renderer_cls:
            instance = renderer_cls.return_value
            self.orch.render()
            renderer_cls.assert_called_once_with(self.orch.stack)
            instance.render.assert_called_once()
            self.orch.docker.reload_gate_nginx.assert_not_called()

    def test_render_reloads_gate_when_stamp_differs_from_disk(self) -> None:
        self.set_edge_only()
        with self.render_with_gate_stamp(
            fingerprint="disk-fp", read="stale-fp", patch_certs=True
        ) as stamp:
            self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_called_once()
        stamp.write.assert_called_once_with("disk-fp")

    def test_render_reloads_gate_when_stamp_missing(self) -> None:
        """Disk already has config but gate never recorded a reload (stale process)."""
        self.set_edge_only()
        with self.render_with_gate_stamp(fingerprint="on-disk", read=None, patch_certs=True):
            self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_called_once()

    def test_render_blocks_gate_reload_when_origin_certs_missing(self) -> None:
        write_applied_app(self.tmp_path, "app", public_host="app.test", tls="origin")
        orch = self.orchestrator()
        self.set_edge_only(orch=orch)
        with self.render_with_gate_stamp(fingerprint="disk-fp", read="stale"):
            with pytest.raises(RuntimeError, match="Origin certs missing"):
                orch.render()
        orch.docker.reload_gate_nginx.assert_not_called()

    def test_render_skips_gate_reload_when_stamp_matches_disk(self) -> None:
        self.set_edge_only()
        with self.render_with_gate_stamp(fingerprint="same", read="same"):
            self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_not_called()

    def test_render_skips_gate_reload_when_gate_down(self) -> None:
        self.set_running(*RunningServices.router_only())
        with self.render_with_gate_stamp(fingerprint="disk-fp", read="stale"):
            self.orch.render()
        self.orch.docker.reload_gate_nginx.assert_not_called()

    def test_start_happy_path(self) -> None:
        self.orch.docker.running_services.side_effect = [
            [],
            RunningServices.with_apps("app"),
        ]
        self.stub_http_ready(self.orch.http)
        with patch.object(self.orch, "sync") as sync:
            self.orch.start()
        sync.assert_called_once()
        self.orch.docker.start_stack.assert_called_once()
        self.orch.docker.reload_router_nginx.assert_called_once()
        events = GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
        assert [e.kind for e in events] == [KIND_UP]

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
        self.set_edge_only()
        self.stub_http_ready(self.orch.http)
        with patch.object(self.orch, "render"):
            self.orch.recreate_gate()
        self.orch.docker.recreate_gate.assert_called_once()
        events = GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
        assert [e.kind for e in events] == [KIND_GATE_RECREATE]

    def test_stop_already_stopped(self) -> None:
        self.orch.docker.running_services.side_effect = [[], []]
        self.orch.docker.network_holders.return_value = []
        self.orch.stop()
        self.orch.docker.remove_container.assert_called()
        self.orch.docker.stop_stack.assert_called_once()

    def test_stop_after_down_does_not_raise_service_not_running(self, capsys) -> None:
        """Regression: assert-stopped must not require a running router."""
        orch = self.orchestrator(mock_deps=False)
        shell = MagicMock()
        orch.docker = DockerStack(orch.stack, shell)
        shell.compose.return_value = completed("")
        shell.docker.return_value = completed("", returncode=1)
        orch.stop()
        text = capsys.readouterr().out + capsys.readouterr().err
        assert "stack already stopped" in text
        assert "not running" not in text

    def test_stop_running(self) -> None:
        self.orch.docker.running_services.side_effect = [
            list(RunningServices.gate_only()),
            [],
        ]
        self.orch.docker.network_holders.return_value = []
        self.orch.stop()
        self.orch.docker.stop_stack.assert_called_once()
        events = GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
        assert [e.kind for e in events] == [KIND_DOWN]

    def test_stop_incomplete_raises(self) -> None:
        self.orch.docker.running_services.side_effect = [
            list(RunningServices.gate_only()),
            list(RunningServices.gate_only()),
        ]
        self.orch.docker.network_holders.return_value = ["raft-raft-gate-1"]
        with pytest.raises(OperatorError, match="did not fully stop"):
            self.orch.stop()

    def test_stop_warns_when_network_still_held(self, capsys) -> None:
        self.orch.docker.running_services.side_effect = [
            list(RunningServices.gate_only()),
            [],
        ]
        self.orch.docker.network_holders.return_value = ["sneaky"]
        self.orch.stop()
        captured = capsys.readouterr()
        text = captured.out + captured.err
        assert "network still has containers" in text
        assert "sneaky" in text

    def test_redeploy_routes_to_router_and_app(self) -> None:
        with patch.object(self.orch, "redeploy_router") as rr:
            self.orch.redeploy("router")
        rr.assert_called_once()
        with patch.object(self.orch, "redeploy_app") as ra:
            self.orch.redeploy("app")
        ra.assert_called_once_with("app")

    def test_redeploy_router_happy(self) -> None:
        self.set_edge_only()
        self.stub_http_ready(self.orch.http)
        self.orch.redeploy_router()
        self.orch.docker.recreate_router.assert_called_once()
        events = GraphEventStore(self.tmp_path).events_in_window(from_ts=_EPOCH)
        assert len(events) == 1
        assert events[0].kind == KIND_DEPLOYMENT
        assert events[0].service == "raft-router"
        assert events[0].label == "Redeploy router"
