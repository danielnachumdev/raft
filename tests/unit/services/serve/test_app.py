"""App factory + route smoke tests for ``raft serve``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from raft.models import EDGE_GROUP
from raft.services.ops.status.models import StatusSnapshot
from raft.services.serve.app import ServeAppFactory
from raft.services.serve.service import DEFAULT_SERVE_PORT, Serve

from ...base import RaftTestCase, make_stack
from ...services.ops.status.fixtures import StatusFixtures


class _ServeFixtures:
    @staticmethod
    def full_snapshot() -> StatusSnapshot:
        fx = StatusFixtures
        return StatusSnapshot(
            host=fx.empty_host_status(),
            containers=(
                fx.container("raft-gate", role="gate", group=EDGE_GROUP),
                fx.container("raft-router", role="router", group=EDGE_GROUP),
                fx.container("raft-controller", role="controller", group=EDGE_GROUP),
                fx.container("site", role="app", app="site", status="not running", uptime=None),
            ),
        )

    @staticmethod
    def empty_snapshot() -> StatusSnapshot:
        return StatusSnapshot(host=StatusFixtures.empty_host_status(), containers=())

    @staticmethod
    def client(stack, snapshot: StatusSnapshot) -> TestClient:
        status = MagicMock()
        status.collect.return_value = snapshot
        return TestClient(ServeAppFactory(stack, status=status).create())


class TestServeAppFactory(RaftTestCase):
    def test_index_renders_control_plane_and_apps(self) -> None:
        client = _ServeFixtures.client(make_stack(self.tmp_path), _ServeFixtures.full_snapshot())
        response = client.get("/")
        body = response.text
        assert response.status_code == 200
        assert "Control plane" in body and "gate" in body and "router" in body
        assert "controller" in body and "site" in body
        assert 'id="trends"' in body and "issue #9" in body

    def test_static_css_is_served(self) -> None:
        client = _ServeFixtures.client(make_stack(self.tmp_path), _ServeFixtures.empty_snapshot())
        response = client.get("/static/style.css")
        assert response.status_code == 200
        assert "color-scheme" in response.text

    def test_index_empty_snapshot_placeholders(self) -> None:
        client = _ServeFixtures.client(make_stack(self.tmp_path), _ServeFixtures.empty_snapshot())
        body = client.get("/").text
        assert "No control-plane services" in body
        assert "No applied apps" in body

    def test_factory_builds_default_status(self) -> None:
        stack = make_stack(self.tmp_path)
        with patch("raft.services.serve.page.Status") as status_cls:
            status_cls.return_value = MagicMock()
            ServeAppFactory(stack).create()
        status_cls.assert_called_once_with(stack)


class TestServeRun(RaftTestCase):
    def test_run_prints_instructions_and_starts_uvicorn(self, capsys) -> None:
        with patch("raft.services.serve.service.uvicorn.run") as run:
            Serve(make_stack(self.tmp_path)).run(port=DEFAULT_SERVE_PORT)
        out = capsys.readouterr().out
        assert "http://127.0.0.1:8787/" in out
        assert "ssh -L 8787:127.0.0.1:8787" in out
        run.assert_called_once()
        args, kwargs = run.call_args
        assert kwargs["host"] == "127.0.0.1" and kwargs["port"] == 8787
        assert args[0] is not None
